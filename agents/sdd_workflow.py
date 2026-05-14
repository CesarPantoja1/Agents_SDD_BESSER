from typing import Literal
from langgraph.graph import StateGraph, START, END, MessagesState
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import os
import pathlib

from langdetect import detect

from sdd_prompts import (
    FaseOutput,
    ArtefactoOutput,
    ImpactoOutput,
    ValidacionPreviaOutput,
    ValidacionPostGenOutput,
    build_system_prompt_clasificador,
    build_impact_analysis_prompt,
    build_validation_prompt,
    build_post_validation_prompt,
    _construir_prompt_generador,
    _construir_prompt_sync,
    _mostrar_impacto,
    _mostrar_validacion_previa,
)

from besser_schemas import SystemClassSpec
from besser_layout import layout_class_system
import json


# ---------------------------------------------------------------------------
# 0. Helpers
# ---------------------------------------------------------------------------
SCRIPT_DIR = pathlib.Path(__file__).parent


def _detectar_idioma(texto: str) -> str:
    """Detecta el idioma del texto de forma determinística.

    Para textos muy cortos (< 30 chars) usa heurística en lugar de langdetect
    porque la librería es propensa a falsos positivos con pocas palabras.
    """
    t = texto.strip()
    if len(t) < 30:
        # Heurística rápida para español vs otros idiomas europeos
        lower = t.lower()
        spanish_markers = ["ñ", "á", "é", "í", "ó", "ú", "ü", "quiero", "haz", "genera", "diagrama", "listo", "continuar", "siguiente"]
        if any(m in lower for m in spanish_markers):
            return "es"
        # Si no hay marcadores, asumimos español por defecto (proyecto hispanohablante)
        return "es"
    try:
        return detect(t)
    except Exception:
        return "es"


def _load_spec(*parts: str) -> str:
    path = SCRIPT_DIR.joinpath("especificaciones", *parts)
    return path.read_text(encoding="utf-8")


def _guardar_artefacto(nombre: str, contenido: str):
    output_dir = SCRIPT_DIR / "output"
    output_dir.mkdir(exist_ok=True)
    path = output_dir / f"{nombre}.md"
    path.write_text(contenido, encoding="utf-8")
    print(f"   💾 Guardado en: {path}")


def _guardar_diagrama_json(contenido_json: str):
    output_dir = SCRIPT_DIR / "output"
    output_dir.mkdir(exist_ok=True)
    path = output_dir / "class-diagram.json"
    path.write_text(contenido_json, encoding="utf-8")
    print(f"   💾 Diagrama guardado en: {path}")


def _analizar_impacto_llm(
    fase_modificada: str,
    old_content: str | None,
    new_content: str,
    product_content: str | None,
    discovery_content: str | None,
    requirements_content: str | None,
    design_content: str | None,
    diagram_content: str | None,
) -> ImpactoOutput | None:
    """Usa el LLM para analizar si un cambio impacta artefactos posteriores y si es consistente con anteriores."""
    if not old_content:
        return None

    prompt = build_impact_analysis_prompt(
        fase_modificada=fase_modificada,
        old_content=old_content,
        new_content=new_content,
        product_content=product_content,
        discovery_content=discovery_content,
        requirements_content=requirements_content,
        design_content=design_content,
        diagram_content=diagram_content,
    )

    try:
        resultado: ImpactoOutput = structured_llm_impacto.invoke(prompt)
    except Exception as e:
        print(f"   ⚠️ Error en análisis de impacto: {e}")
        return None

    # Override downstream impact for non-existent artifacts
    orden = ["product", "discovery", "requirements", "design", "diagram"]
    idx_mod = orden.index(fase_modificada)
    contents = {
        "discovery": discovery_content,
        "requirements": requirements_content,
        "design": design_content,
        "diagram": diagram_content,
    }
    for fase in orden[idx_mod + 1 :]:
        if not contents.get(fase):
            setattr(resultado, f"impacta_{fase}", False)
            setattr(
                resultado,
                f"razon_{fase}",
                "Artefacto no generado todavía, no requiere sincronización.",
            )

    return resultado


# ---------------------------------------------------------------------------
# 1. Schemas estrictos (importados desde sdd_prompts)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 2. Modelo Gemini
# ---------------------------------------------------------------------------
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.2,
    google_api_key="AIzaSyCIpP38x7zZHQ-03WOTrBJhAmbdcW1ZQyg",
)

structured_llm_fase = llm.with_structured_output(FaseOutput)
structured_llm_artefacto = llm.with_structured_output(ArtefactoOutput)
structured_llm_impacto = llm.with_structured_output(ImpactoOutput)
structured_llm_validacion = llm.with_structured_output(ValidacionPreviaOutput)
structured_llm_post_validacion = llm.with_structured_output(ValidacionPostGenOutput)
structured_llm_diagram = llm.with_structured_output(SystemClassSpec)


# ---------------------------------------------------------------------------
# 3. System prompt del clasificador (importado desde sdd_prompts)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 4. Estado del grafo
# ---------------------------------------------------------------------------
class State(MessagesState):
    fase: Literal[
        "product", "discovery", "requirements", "design", "diagram",
        "next", "sync", "error",
        "validation_reject", "validation_apply", "validation_sync",
    ] | None = None
    product_content: str | None = None
    product_content_prev: str | None = None
    discovery_content: str | None = None
    discovery_content_prev: str | None = None
    requirements_content: str | None = None
    requirements_content_prev: str | None = None
    design_content: str | None = None
    design_content_prev: str | None = None
    diagram_content: str | None = None
    diagram_content_prev: str | None = None
    blocked_reason: str | None = None
    last_active_phase: Literal["product", "discovery", "requirements", "design", "diagram", "sync"] | None = None
    sync_target: Literal["discovery", "requirements", "design", "diagram"] | None = None
    impacto_analysis: dict | None = None
    # Campos para validación previa (2-turn flow)
    pending_validation: dict | None = None
    pending_intention: str | None = None
    pending_fase: str | None = None
    skip_validation: bool = False
    sync_after_generate: bool = False


# ---------------------------------------------------------------------------
# 5. Validación previa (Approval Gate)
# ---------------------------------------------------------------------------
def _validar_consistencia_previa(
    fase_destino: str,
    intencion_usuario: str,
    state: dict,
) -> ValidacionPreviaOutput | None:
    """Valida la intención del usuario antes de generar. Retorna None si no hay artefactos en otras fases."""

    orden = ["product", "discovery", "requirements", "design", "diagram"]
    idx_dest = orden.index(fase_destino)

    # Verificar si hay artefactos en OTRAS fases (upstream o downstream)
    hay_otras_fases = False
    for i, fase in enumerate(orden):
        if i == idx_dest:
            continue
        if state.get(f"{fase}_content"):
            hay_otras_fases = True
            break

    if not hay_otras_fases:
        return None  # No hay otras especificaciones, no puede haber inconsistencias

    prompt = build_validation_prompt(
        fase_destino=fase_destino,
        intencion_usuario=intencion_usuario,
        product_content=state.get("product_content"),
        discovery_content=state.get("discovery_content"),
        requirements_content=state.get("requirements_content"),
        design_content=state.get("design_content"),
        diagram_content=state.get("diagram_content"),
    )

    try:
        resultado: ValidacionPreviaOutput = structured_llm_validacion.invoke(prompt)
        return resultado
    except Exception as e:
        print(f"   ⚠️ Error en validación previa: {e}")
        return None


def _preguntar_usuario_aprobacion(validacion: ValidacionPreviaOutput) -> bool:
    """Muestra inconsistencias y retorna False para que el nodo guarde estado pendiente."""
    if not _mostrar_validacion_previa(validacion):
        print("\n💬 Escribe tu decisión:")
        print("   • 'rechazar' → cancela la generación")
        print("   • 'aplicar igual' → genera a pesar de las inconsistencias")
        print("   • 'sincronizar' → genera y ajusta las especificaciones afectadas")
        return False
    return True


def _validar_post_generacion(
    fase_modificada: str,
    old_content: str | None,
    new_content: str,
    state: dict,
) -> ValidacionPostGenOutput | None:
    """Valida un artefacto YA GENERADO contra otras fases existentes."""

    orden = ["product", "discovery", "requirements", "design", "diagram"]
    idx_mod = orden.index(fase_modificada)

    # Solo validar si hay al menos otra fase existente
    hay_otras = False
    for i, fase in enumerate(orden):
        if i != idx_mod and state.get(f"{fase}_content"):
            hay_otras = True
            break

    if not hay_otras:
        return None  # No hay otras fases para comparar

    prompt = build_post_validation_prompt(
        fase_modificada=fase_modificada,
        old_content=old_content,
        new_content=new_content,
        product_content=state.get("product_content") if fase_modificada != "product" else None,
        discovery_content=state.get("discovery_content") if fase_modificada != "discovery" else None,
        requirements_content=state.get("requirements_content") if fase_modificada != "requirements" else None,
        design_content=state.get("design_content") if fase_modificada != "design" else None,
        diagram_content=state.get("diagram_content") if fase_modificada != "diagram" else None,
    )

    try:
        resultado: ValidacionPostGenOutput = structured_llm_post_validacion.invoke(prompt)
        return resultado
    except Exception as e:
        print(f"   ⚠️ Error en validación post-generación: {e}")
        return None


def _sincronizar_todo(
    state: dict,
    fase_generada: str,
    old_content: str | None,
    new_content: str,
) -> dict:
    """Sincroniza artefactos upstream y downstream tras una generación. Retorna dict con cambios."""
    print(f"\n🔄 Sincronizando especificaciones afectadas por cambio en {fase_generada.upper()}...")
    resultados = {}
    orden = ["product", "discovery", "requirements", "design", "diagram"]
    idx_gen = orden.index(fase_generada)

    # --- 1. SINCRONIZAR UPSTREAM (fases anteriores) ---
    for i in range(idx_gen - 1, -1, -1):
        fase_up = orden[i]
        contenido_up = state.get(f"{fase_up}_content")
        if not contenido_up:
            continue

        prompt = (
            "Eres un editor quirúrgico de especificaciones. "
            "Haz el CAMBIO MÍNIMO NECESARIO para restaurar consistencia. "
            "NO reescribas secciones que no cambian. "
            "MANTÉN TODO el contenido existente excepto lo que DEBE cambiar.\n\n"
            f"El artefacto {fase_generada.upper()} fue modificado.\n\n"
            f"CONTENIDO ANTERIOR DE {fase_generada.upper()}:\n"
            f"{old_content[:2000] if old_content else '(nuevo artefacto)'}\n\n"
            f"CONTENIDO NUEVO DE {fase_generada.upper()}:\n"
            f"{new_content[:2000]}\n\n"
            f"ARTEFACTO {fase_up.upper()} A ACTUALIZAR:\n"
            f"{contenido_up[:3000]}\n\n"
            f"INSTRUCCIONES:\n"
            f"1. Analiza qué cambió en {fase_generada.upper()}.\n"
            f"2. Determina si ese cambio requiere modificar {fase_up.upper()}.\n"
            f"3. Si NO requiere cambios, devuelve el artefacto {fase_up.upper()} EXACTAMENTE igual.\n"
            f"4. Si SÍ requiere cambios, haz SOLO el cambio mínimo necesario.\n"
            f"5. Devuelve el documento COMPLETO (modificado o sin cambios)."
        )

        try:
            resultado: ArtefactoOutput = structured_llm_artefacto.invoke(prompt)
            # Solo guardar si realmente cambió
            if resultado.contenido.strip() != contenido_up.strip():
                if fase_up == "diagram":
                    _guardar_diagrama_json(resultado.contenido)
                else:
                    _guardar_artefacto(fase_up, resultado.contenido)
                resultados[f"{fase_up}_content"] = resultado.contenido
                resultados[f"{fase_up}_content_prev"] = contenido_up
                print(f"   ✅ {fase_up.upper()} sincronizado (upstream).")
            else:
                print(f"   ✅ {fase_up.upper()} sin cambios necesarios (upstream).")
        except Exception as e:
            print(f"   ⚠️ Error sincronizando {fase_up.upper()} (upstream): {e}")

    # --- 2. SINCRONIZAR DOWNSTREAM (fases posteriores) ---
    for i in range(idx_gen + 1, len(orden)):
        fase_down = orden[i]
        contenido_down = state.get(f"{fase_down}_content")
        if not contenido_down:
            continue

        # Determinar template y guards
        if fase_down == "discovery":
            template = _load_spec("discovery", "dicovery.md")
            guards = _load_spec("guards-discovery.md")
        elif fase_down == "requirements":
            template = _load_spec("requirements", "requirements.md")
            ears = _load_spec("requirements", "ears-format.md")
            review = _load_spec("requirements", "requirements-review-gate.md")
            guards = _load_spec("guards-requirements.md")
            template = template + "\n\n" + ears + "\n\n" + review + "\n\n" + guards
        elif fase_down == "design":
            template = _load_spec("design", "design.md")
            guards = _load_spec("guards-design.md")
        elif fase_down == "diagram":
            # Diagram no usa template markdown; se genera vía LLM structured output
            # No sincronizamos downstream de diagram porque es la hoja
            continue
        else:
            continue

        idioma = _detectar_idioma(new_content)
        razones = f"Cambio en {fase_generada.upper()} requiere actualización."

        messages = _construir_prompt_sync(
            fase_objetivo=fase_down,
            fase_modificada=fase_generada,
            contenido_modificado=new_content,
            contenido_objetivo_actual=contenido_down,
            razones_sync=razones,
            template=template,
            guards=guards,
            idioma=idioma,
        )

        try:
            print(f"🔄 Sincronizando {fase_down.upper()} (downstream)...")
            resultado: ArtefactoOutput = structured_llm_artefacto.invoke(messages)
            if resultado.contenido.strip() != contenido_down.strip():
                _guardar_artefacto(fase_down, resultado.contenido)
                resultados[f"{fase_down}_content"] = resultado.contenido
                resultados[f"{fase_down}_content_prev"] = contenido_down
                print(f"   ✅ {fase_down.upper()} sincronizado (downstream).")
            else:
                print(f"   ✅ {fase_down.upper()} sin cambios necesarios (downstream).")
        except Exception as e:
            print(f"   ⚠️ Error sincronizando {fase_down.upper()} (downstream): {e}")

    if resultados:
        print(f"\n📄 Sincronización completada.")
    else:
        print(f"\n✅ Ninguna especificación requirió sincronización.")
    return resultados


# ---------------------------------------------------------------------------
# 6. Nodos
# ---------------------------------------------------------------------------
def nodo_clasificador(state: State):
    """Detecta la intención del usuario y setea la fase."""
    system_msg = build_system_prompt_clasificador(
        last_active_phase=state.get("last_active_phase"),
        has_product=bool(state.get("product_content")),
        has_discovery=bool(state.get("discovery_content")),
        has_requirements=bool(state.get("requirements_content")),
        has_design=bool(state.get("design_content")),
        has_diagram=bool(state.get("diagram_content")),
        has_pending_validation=bool(state.get("pending_validation")),
    )
    messages = [system_msg] + state["messages"]
    resultado: FaseOutput = structured_llm_fase.invoke(messages)
    return {"fase": resultado.fase}


def nodo_validador(state: State):
    """Verifica dependencias de fases y resuelve 'next' de forma determinística."""
    fase = state["fase"]

    if fase == "next":
        if not state.get("product_content"):
            return {"fase": "product", "blocked_reason": None}
        if not state.get("discovery_content"):
            return {"fase": "discovery", "blocked_reason": None}
        if not state.get("requirements_content"):
            return {"fase": "requirements", "blocked_reason": None}
        if not state.get("design_content"):
            return {"fase": "design", "blocked_reason": None}
        if not state.get("diagram_content"):
            return {"fase": "diagram", "blocked_reason": None}
        return {
            "fase": "error",
            "blocked_reason": (
                "Todas las fases del flujo SDD ya están completas (Product, Discovery, Requirements, Design, Diagram). "
                "No hay un siguiente paso al que continuar."
            ),
        }

    if fase == "product":
        return {"blocked_reason": None}

    if fase == "discovery":
        if not state.get("product_content"):
            return {
                "blocked_reason": (
                    "No puedes generar Discovery todavía. "
                    "Primero debes completar la fase de Product."
                )
            }
        return {"blocked_reason": None}

    if fase == "requirements":
        if not state.get("discovery_content"):
            return {
                "blocked_reason": (
                    "No puedes generar Requirements todavía. "
                    "Primero debes completar la fase de Discovery."
                )
            }
        return {"blocked_reason": None}

    if fase == "design":
        faltantes = []
        if not state.get("discovery_content"):
            faltantes.append("Discovery")
        if not state.get("requirements_content"):
            faltantes.append("Requirements")
        if faltantes:
            return {
                "blocked_reason": (
                    f"No puedes generar Design todavía. "
                    f"Te faltan: {', '.join(faltantes)}."
                )
            }
        return {"blocked_reason": None}

    if fase == "diagram":
        faltantes = []
        if not state.get("discovery_content"):
            faltantes.append("Discovery")
        if not state.get("requirements_content"):
            faltantes.append("Requirements")
        if not state.get("design_content"):
            faltantes.append("Design")
        if faltantes:
            return {
                "blocked_reason": (
                    f"No puedes generar Diagram todavía. "
                    f"Te faltan: {', '.join(faltantes)}."
                )
            }
        return {"blocked_reason": None}

    if fase == "sync":
        return {"blocked_reason": None}

    if fase == "error":
        return {"blocked_reason": None}

    return {"blocked_reason": f"Fase desconocida: {fase}"}


def nodo_bloqueado(state: State):
    print(f"⛔ Avance bloqueado: {state['blocked_reason']}")
    return {}


def nodo_error(state: State):
    print("❌ Llegó al nodo: ERROR (mensaje incoherente o fuera de contexto)")
    return {}


# ---------------------------------------------------------------------------
# 6. Nodos generadores (con guards en prompt, sin validación post)
# ---------------------------------------------------------------------------
def nodo_product(state: State):
    print("✅ Llegó al nodo: PRODUCT")

    old_content = state.get("product_content")
    user_message = state["messages"][-1].content
    idioma = _detectar_idioma(user_message)

    template = _load_spec("product", "product.md")
    guards = _load_spec("guards-product.md")

    messages = _construir_prompt_generador(
        template=template,
        guards=guards,
        user_message=user_message,
        idioma=idioma,
        artefacto_actual=old_content,
    )

    resultado: ArtefactoOutput = structured_llm_artefacto.invoke(messages)
    new_content = resultado.contenido
    _guardar_artefacto("product", new_content)

    # Validación POST-GENERACIÓN: comparar contra otras fases existentes
    validacion = _validar_post_generacion(
        fase_modificada="product",
        old_content=old_content,
        new_content=new_content,
        state=state,
    )
    if validacion and not validacion.es_valido:
        print(f"\n⚠️  Se detectaron inconsistencias post-generación en PRODUCT.")
        return {
            "product_content": new_content,
            "product_content_prev": old_content,
            "last_active_phase": "product",
            "pending_validation": validacion.model_dump(),
            "pending_intention": user_message,
            "pending_fase": "product",
            "skip_validation": False,
            "sync_after_generate": False,
        }

    # Análisis de impacto con IA
    if old_content:
        impacto = _analizar_impacto_llm(
            fase_modificada="product",
            old_content=old_content,
            new_content=new_content,
            product_content=None,
            discovery_content=state.get("discovery_content"),
            requirements_content=state.get("requirements_content"),
            design_content=state.get("design_content"),
            diagram_content=state.get("diagram_content"),
        )
        if impacto:
            _mostrar_impacto(impacto, "product")
            impacto_dict = impacto.model_dump()
        else:
            impacto_dict = None
    else:
        print("\n✅ Product creado por primera vez. No hay artefactos posteriores para analizar.")
        impacto_dict = None

    ret = {
        "product_content": new_content,
        "product_content_prev": old_content,
        "last_active_phase": "product",
        "impacto_analysis": impacto_dict,
        "skip_validation": False,
        "sync_after_generate": False,
    }
    if state.get("sync_after_generate"):
        sync_results = _sincronizar_todo(state, "product", old_content, new_content)
        ret.update(sync_results)
    return ret


def nodo_discovery(state: State):
    print("✅ Llegó al nodo: DISCOVERY")

    old_content = state.get("discovery_content")
    user_message = state["messages"][-1].content
    idioma = _detectar_idioma(user_message)

    template = _load_spec("discovery", "dicovery.md")
    guards = _load_spec("guards-discovery.md")

    partes_contexto = []
    if state.get("product_content"):
        partes_contexto.append(f"### Product (fuente de verdad para visión y use cases)\n{state['product_content']}")
    contexto = "\n\n".join(partes_contexto) if partes_contexto else None

    messages = _construir_prompt_generador(
        template=template,
        guards=guards,
        user_message=user_message,
        idioma=idioma,
        contexto_previo=contexto,
        artefacto_actual=old_content,
    )

    resultado: ArtefactoOutput = structured_llm_artefacto.invoke(messages)
    new_content = resultado.contenido
    _guardar_artefacto("discovery", new_content)

    # Validación POST-GENERACIÓN: comparar contra otras fases existentes
    validacion = _validar_post_generacion(
        fase_modificada="discovery",
        old_content=old_content,
        new_content=new_content,
        state=state,
    )
    if validacion and not validacion.es_valido:
        print(f"\n⚠️  Se detectaron inconsistencias post-generación en DISCOVERY.")
        return {
            "discovery_content": new_content,
            "discovery_content_prev": old_content,
            "last_active_phase": "discovery",
            "pending_validation": validacion.model_dump(),
            "pending_intention": user_message,
            "pending_fase": "discovery",
            "skip_validation": False,
            "sync_after_generate": False,
        }

    # Análisis de impacto con IA
    if old_content:
        impacto = _analizar_impacto_llm(
            fase_modificada="discovery",
            old_content=old_content,
            new_content=new_content,
            product_content=state.get("product_content"),
            discovery_content=None,
            requirements_content=state.get("requirements_content"),
            design_content=state.get("design_content"),
            diagram_content=state.get("diagram_content"),
        )
        if impacto:
            _mostrar_impacto(impacto, "discovery")
            impacto_dict = impacto.model_dump()
        else:
            impacto_dict = None
    else:
        print("\n✅ Discovery creado por primera vez. No hay artefactos posteriores para analizar.")
        impacto_dict = None

    ret = {
        "discovery_content": new_content,
        "discovery_content_prev": old_content,
        "last_active_phase": "discovery",
        "impacto_analysis": impacto_dict,
        "skip_validation": False,
        "sync_after_generate": False,
    }
    if state.get("sync_after_generate"):
        sync_results = _sincronizar_todo(state, "discovery", old_content, new_content)
        ret.update(sync_results)
    return ret


def nodo_requirements(state: State):
    print("✅ Llegó al nodo: REQUIREMENTS")

    old_content = state.get("requirements_content")
    user_message = state["messages"][-1].content
    idioma = _detectar_idioma(user_message)

    template = _load_spec("requirements", "requirements.md")
    ears = _load_spec("requirements", "ears-format.md")
    review = _load_spec("requirements", "requirements-review-gate.md")
    guards = _load_spec("guards-requirements.md")

    # Unir template + EARS + review gate + guards
    template_completo = template + "\n\n" + ears + "\n\n" + review + "\n\n" + guards

    contexto = None
    if state.get("discovery_content"):
        contexto = f"### Discovery (fuente de verdad para Scope In/Out)\n{state['discovery_content']}"

    messages = _construir_prompt_generador(
        template=template_completo,
        guards=guards,
        user_message=user_message,
        idioma=idioma,
        contexto_previo=contexto,
        artefacto_actual=old_content,
    )

    resultado: ArtefactoOutput = structured_llm_artefacto.invoke(messages)
    new_content = resultado.contenido
    _guardar_artefacto("requirements", new_content)

    # Validación POST-GENERACIÓN: comparar contra otras fases existentes
    validacion = _validar_post_generacion(
        fase_modificada="requirements",
        old_content=old_content,
        new_content=new_content,
        state=state,
    )
    if validacion and not validacion.es_valido:
        print(f"\n⚠️  Se detectaron inconsistencias post-generación en REQUIREMENTS.")
        return {
            "requirements_content": new_content,
            "requirements_content_prev": old_content,
            "last_active_phase": "requirements",
            "pending_validation": validacion.model_dump(),
            "pending_intention": user_message,
            "pending_fase": "requirements",
            "skip_validation": False,
            "sync_after_generate": False,
        }

    # Análisis de impacto con IA
    if old_content:
        impacto = _analizar_impacto_llm(
            fase_modificada="requirements",
            old_content=old_content,
            new_content=new_content,
            product_content=state.get("product_content"),
            discovery_content=state.get("discovery_content"),
            requirements_content=None,
            design_content=state.get("design_content"),
            diagram_content=state.get("diagram_content"),
        )
        if impacto:
            _mostrar_impacto(impacto, "requirements")
            impacto_dict = impacto.model_dump()
        else:
            impacto_dict = None
    else:
        print("\n✅ Requirements creado por primera vez. No hay artefactos posteriores para analizar.")
        impacto_dict = None

    ret = {
        "requirements_content": new_content,
        "requirements_content_prev": old_content,
        "last_active_phase": "requirements",
        "impacto_analysis": impacto_dict,
        "skip_validation": False,
        "sync_after_generate": False,
    }
    if state.get("sync_after_generate"):
        sync_results = _sincronizar_todo(state, "requirements", old_content, new_content)
        ret.update(sync_results)
    return ret


def nodo_design(state: State):
    print("✅ Llegó al nodo: DESIGN")

    old_content = state.get("design_content")
    user_message = state["messages"][-1].content
    idioma = _detectar_idioma(user_message)

    template = _load_spec("design", "design.md")
    guards = _load_spec("guards-design.md")

    partes_contexto = []
    if state.get("discovery_content"):
        partes_contexto.append(f"### Discovery (fuente de verdad para Approach/Stack)\n{state['discovery_content']}")
    if state.get("requirements_content"):
        partes_contexto.append(f"### Requirements (fuente de verdad para Req IDs)\n{state['requirements_content']}")
    contexto = "\n\n".join(partes_contexto) if partes_contexto else None

    messages = _construir_prompt_generador(
        template=template,
        guards=guards,
        user_message=user_message,
        idioma=idioma,
        contexto_previo=contexto,
        artefacto_actual=old_content,
    )

    resultado: ArtefactoOutput = structured_llm_artefacto.invoke(messages)
    new_content = resultado.contenido
    _guardar_artefacto("design", new_content)

    # Validación POST-GENERACIÓN: comparar contra otras fases existentes
    validacion = _validar_post_generacion(
        fase_modificada="design",
        old_content=old_content,
        new_content=new_content,
        state=state,
    )
    if validacion and not validacion.es_valido:
        print(f"\n⚠️  Se detectaron inconsistencias post-generación en DESIGN.")
        return {
            "design_content": new_content,
            "design_content_prev": old_content,
            "last_active_phase": "design",
            "pending_validation": validacion.model_dump(),
            "pending_intention": user_message,
            "pending_fase": "design",
            "skip_validation": False,
            "sync_after_generate": False,
        }

    # Análisis de impacto con IA
    # Design tiene Diagram como fase posterior.
    if old_content:
        impacto = _analizar_impacto_llm(
            fase_modificada="design",
            old_content=old_content,
            new_content=new_content,
            product_content=state.get("product_content"),
            discovery_content=state.get("discovery_content"),
            requirements_content=state.get("requirements_content"),
            design_content=None,
            diagram_content=state.get("diagram_content"),
        )
        if impacto:
            _mostrar_impacto(impacto, "design")
            impacto_dict = impacto.model_dump()
        else:
            impacto_dict = None
    else:
        print("\n✅ Design creado por primera vez.")
        impacto_dict = None

    ret = {
        "design_content": new_content,
        "design_content_prev": old_content,
        "last_active_phase": "design",
        "impacto_analysis": impacto_dict,
        "skip_validation": False,
        "sync_after_generate": False,
    }
    if state.get("sync_after_generate"):
        sync_results = _sincronizar_todo(state, "design", old_content, new_content)
        ret.update(sync_results)
    return ret


def nodo_diagram(state: State):
    print("✅ Llegó al nodo: DIAGRAM (Diagrama de Clases)")

    old_content = state.get("diagram_content")
    user_message = state["messages"][-1].content

    # Detectar idioma de las especificaciones existentes, NO del mensaje corto del usuario
    # (langdetect falla con textos cortos y puede devolver idiomas incorrectos)
    idioma = "es"  # default seguro
    for fase_key in ["product_content", "discovery_content", "requirements_content", "design_content"]:
        content = state.get(fase_key)
        if content and len(content) > 100:
            idioma = _detectar_idioma(content)
            break

    # Construir prompt enriquecido con contexto de todas las fases anteriores
    contexto_parts = []
    if state.get("product_content"):
        contexto_parts.append(f"=== PRODUCT ===\n{state['product_content']}")
    if state.get("discovery_content"):
        contexto_parts.append(f"=== DISCOVERY ===\n{state['discovery_content']}")
    if state.get("requirements_content"):
        contexto_parts.append(f"=== REQUIREMENTS ===\n{state['requirements_content']}")
    if state.get("design_content"):
        contexto_parts.append(f"=== DESIGN ===\n{state['design_content']}")

    contexto = "\n\n".join(contexto_parts)

    system_prompt = (
        "Eres un arquitecto de software senior especializado en modelado UML y diseño orientado a objetos. "
        "Tu tarea es generar un diagrama de clases completo, profesional y alineado con las especificaciones del sistema.\n\n"
        "=== PROCESO DE MODELADO (sigue estos pasos obligatoriamente) ===\n"
        "PASO 1 - Análisis de Requisitos Funcionales:\n"
        "   Lee detalladamente la sección REQUIREMENTS. Identifica cada actor, entidad de dominio, "
        "   objeto de valor y agregado mencionado o implícito en los requisitos funcionales.\n"
        "   Cada requisito que involucre una entidad (ej. 'publicar anuncio', 'enviar mensaje', 'crear usuario') "
        "   DEBE traducirse en al menos una clase del diagrama.\n\n"
        "PASO 2 - Identificación de Clases:\n"
        "   - Entidades principales del dominio (ej. Usuario, Vehículo, Anuncio, Mensaje).\n"
        "   - Objetos de valor (Value Objects) que merezcan clase propia (ej. Dirección, Precio, FiltroBusqueda).\n"
        "   - Enumeraciones para estados, tipos, roles o categorías discretas (ej. EstadoPublicacion, TipoUsuario, Rol).\n"
        "   - Clases de servicio o utilidad SOLO si están explícitamente justificadas en el diseño.\n"
        "   - NO crees clases genéricas sin soporte en los requisitos (ej. 'Database', 'Manager', 'Handler').\n\n"
        "PASO 3 - Definición de Atributos:\n"
        "   Cada clase DEBE tener entre 3 y 8 atributos relevantes al dominio.\n"
        "   - ID único (tipo UUID o int) como primer atributo.\n"
        "   - Campos de negocio esenciales derivados de los requisitos.\n"
        "   - Timestamps (fechaCreacion, fechaActualizacion) cuando aplique.\n"
        "   - Estados o flags booleanos solo si son necesarios.\n"
        "   - NO incluyas atributos derivados que se puedan calcular (salvo que estén explícitos en reqs).\n"
        "   - Usa camelCase para nombres de atributos.\n\n"
        "PASO 4 - Definición de Métodos:\n"
        "   - Omite getters/setters por completo (son implícitos en UML).\n"
        "   - Incluye SOLO métodos de comportamiento de dominio (ej. publicar(), enviar(), validar(), calcularTotal()).\n"
        "   - Cada método debe tener un returnType apropiado (void, boolean, o una clase del dominio).\n"
        "   - Si un método no tiene comportamiento obvio, NO lo incluyas.\n"
        "   - Usa camelCase para nombres de métodos.\n\n"
        "PASO 5 - Relaciones entre Clases:\n"
        "   Analiza cada requisito que implique interacción entre entidades y modela la relación apropiada:\n"
        "   - Association: cuando dos clases se relacionan pero son independientes (ej. Usuario -> Mensaje).\n"
        "   - Composition: cuando una clase NO puede existir sin la otra (parte-todo fuerte).\n"
        "   - Aggregation: cuando una clase puede existir independientemente (parte-todo débil).\n"
        "   - Inheritance: SOLO cuando haya una relación 'es-un' clara y justificada (ej. UsuarioPremium es Usuario).\n"
        "   - SIEMPRE define multiplicidades precisas: 1, 0..1, 0..*, 1..*.\n"
        "   - Evita relaciones redundantes o cíclicas innecesarias.\n\n"
        "PASO 6 - Enumeraciones:\n"
        "   Crea enumeraciones (isEnumeration=true) para:\n"
        "   - Estados de entidades (ej. EstadoPedido: PENDIENTE, ENVIADO, ENTREGADO).\n"
        "   - Tipos o roles (ej. TipoUsuario: COMPRADOR, VENDEDOR, ADMIN).\n"
        "   - Categorías discretas que se repiten en múltiples clases.\n"
        "   - Los valores de enumeración van como atributos SIN tipo (solo name).\n\n"
        "=== REGLAS DE CALIDAD ===\n"
        "1. COHERENCIA CON REQUISITOS: Cada clase, atributo y relación DEBE ser trazable a un requisito funcional.\n"
        "2. COMPLETITUD: No omitas entidades mencionadas en los requisitos (ej. si hay 'notificaciones', debe existir clase Notificacion).\n"
        "3. PROPIEDADES TÉCNICAS: NO incluyas clases de infraestructura (Controller, Service, Repository, DAO).\n"
        "4. NOMENCLATURA: PascalCase para clases, camelCase para atributos/métodos, nombres semánticos y descriptivos.\n"
        "5. VISIBILIDAD: Usa 'public' por defecto; 'private' solo para atributos sensibles; 'protected' solo con herencia.\n"
        "6. AUSENCIA DE POSICIONES: NO incluyas campo 'position' en ninguna clase; el layout engine las calcula.\n"
        "7. IDIOMA: Genera TODO el contenido del diagrama en el idioma del proyecto.\n\n"
        f"=== REGLA DE IDIOMA ===\n"
        f"El proyecto está en idioma: '{idioma}'.\n"
        f"TODOS los nombres de clases, atributos, métodos y relaciones DEBEN estar en '{idioma}'.\n"
        "Ejemplo en español: clase 'Usuario', atributo 'nombreCompleto', método 'publicarAnuncio()'.\n"
        "Ejemplo en inglés: clase 'User', atributo 'fullName', método 'publishListing()'.\n"
        "NUNCA mezcles idiomas. NUNCA uses inglés si el proyecto está en español.\n"
    )

    user_prompt = (
        f"{contexto}\n\n"
        "=== INSTRUCCIÓN DE GENERACIÓN ===\n"
        f"Solicitud del usuario: {user_message}\n\n"
        "Sigue el PROCESO DE MODELADO definido en las instrucciones del sistema (Pasos 1-6). "
        "Analiza ESPECÍFICAMENTE la sección REQUIREMENTS para identificar todas las entidades del dominio. "
        "Luego, complementa con PRODUCT (visión de negocio), DISCOVERY (scope y stack) y DESIGN (componentes y modelos de datos) "
        "para enriquecer atributos y relaciones que no estén explícitos en los requisitos.\n\n"
        "PASO A PASO (piensa antes de generar):\n"
        "1. Enumera mentalmente todas las entidades que aparecen en los requisitos funcionales.\n"
        "2. Para cada entidad, define sus atributos de negocio más importantes.\n"
        "3. Identifica enumeraciones necesarias (estados, tipos, roles).\n"
        "4. Establece las relaciones entre entidades con multiplicidades precisas.\n"
        "5. Revisa que NO falte ninguna entidad mencionada en los requisitos.\n"
        "6. Genera el diagrama completo siguiendo el schema estructurado requerido.\n\n"
        "Genera el diagrama de clases completo ahora."
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ]

    try:
        resultado: SystemClassSpec = structured_llm_diagram.invoke(messages)
        spec_dict = resultado.model_dump()
    except Exception as e:
        print(f"   ⚠️ Error generando diagrama con LLM: {e}")
        return {"blocked_reason": f"Error generando diagrama: {e}"}

    # Aplicar layout engine de Besser
    try:
        spec_dict = layout_class_system(spec_dict)
    except Exception as e:
        print(f"   ⚠️ Error en layout engine: {e}")
        # Continuamos sin layout (no debería pasar)

    # Convertir a JSON
    new_content = json.dumps(spec_dict, indent=2, ensure_ascii=False)
    _guardar_diagrama_json(new_content)

    # Validación POST-GENERACIÓN: comparar contra otras fases existentes
    validacion = _validar_post_generacion(
        fase_modificada="diagram",
        old_content=old_content,
        new_content=new_content,
        state=state,
    )
    if validacion and not validacion.es_valido:
        print(f"\n⚠️  Se detectaron inconsistencias post-generación en DIAGRAM.")
        return {
            "diagram_content": new_content,
            "diagram_content_prev": old_content,
            "last_active_phase": "diagram",
            "pending_validation": validacion.model_dump(),
            "pending_intention": user_message,
            "pending_fase": "diagram",
            "skip_validation": False,
            "sync_after_generate": False,
        }

    # Análisis de impacto con IA
    # Diagram es la hoja final del árbol, no tiene artefactos posteriores.
    if old_content:
        impacto = _analizar_impacto_llm(
            fase_modificada="diagram",
            old_content=old_content,
            new_content=new_content,
            product_content=state.get("product_content"),
            discovery_content=state.get("discovery_content"),
            requirements_content=state.get("requirements_content"),
            design_content=state.get("design_content"),
            diagram_content=None,
        )
        if impacto:
            _mostrar_impacto(impacto, "diagram")
            impacto_dict = impacto.model_dump()
        else:
            impacto_dict = None
    else:
        print("\n✅ Diagrama de clases creado por primera vez.")
        impacto_dict = None

    ret = {
        "diagram_content": new_content,
        "diagram_content_prev": old_content,
        "last_active_phase": "diagram",
        "impacto_analysis": impacto_dict,
        "skip_validation": False,
        "sync_after_generate": False,
    }
    if state.get("sync_after_generate"):
        sync_results = _sincronizar_todo(state, "diagram", old_content, new_content)
        ret.update(sync_results)
    return ret


def nodo_sincronizador(state: State):
    print("✅ Llegó al nodo: SINCRONIZADOR")

    mensaje = state["messages"][-1].content
    fase_objetivo = _extraer_fase_sync(mensaje)

    if not fase_objetivo:
        print("❌ No se pudo determinar qué artefacto sincronizar.")
        return {"blocked_reason": "No especificaste qué artefacto sincronizar. Escribe: 'sincronizar discovery' o 'sincronizar todo'."}

    fase_modificada = state.get("last_active_phase")
    if not fase_modificada or fase_modificada == "sync":
        print("❌ No hay un artefacto recientemente modificado para sincronizar.")
        return {"blocked_reason": "No hay un artefacto recientemente modificado. Modifica algo primero."}

    # Determinar qué fases sincronizar
    if fase_objetivo == "todo":
        orden = ["product", "discovery", "requirements", "design", "diagram"]
        idx_mod = orden.index(fase_modificada)
        fases_a_sync = orden[idx_mod + 1:]
    else:
        fases_a_sync = [fase_objetivo]

    resultados = {}
    for fase in fases_a_sync:
        orden = ["product", "discovery", "requirements", "design", "diagram"]
        if orden.index(fase) <= orden.index(fase_modificada):
            print(f"⚠️ {fase.upper()} no es posterior a {fase_modificada.upper()}. Se omite.")
            continue

        contenido_modificado = state.get(f"{fase_modificada}_content")
        if not contenido_modificado:
            print(f"⚠️ No existe contenido para {fase_modificada.upper()}. Se omite {fase}.")
            continue

        contenido_objetivo = state.get(f"{fase}_content")

        impacto = state.get("impacto_analysis", {})
        razones = ""
        if fase == "discovery" and impacto.get("impacta_discovery"):
            razones = impacto.get("razon_discovery", "")
        elif fase == "requirements" and impacto.get("impacta_requirements"):
            razones = impacto.get("razon_requirements", "")
        elif fase == "design" and impacto.get("impacta_design"):
            razones = impacto.get("razon_design", "")

        if not razones and fase_objetivo != "todo":
            print(f"⚠️ El análisis de impacto no indicó que {fase.upper()} requiera sincronización. Sincronizando de todas formas...")
            razones = "Sincronización solicitada por el usuario."

        if fase == "discovery":
            template = _load_spec("discovery", "dicovery.md")
            guards = _load_spec("guards-discovery.md")
        elif fase == "requirements":
            template = _load_spec("requirements", "requirements.md")
            ears = _load_spec("requirements", "ears-format.md")
            review = _load_spec("requirements", "requirements-review-gate.md")
            guards = _load_spec("guards-requirements.md")
            template = template + "\n\n" + ears + "\n\n" + review + "\n\n" + guards
        elif fase == "design":
            template = _load_spec("design", "design.md")
            guards = _load_spec("guards-design.md")
        elif fase == "diagram":
            print("⚠️ Diagram no se sincroniza automáticamente. Regenera el diagrama con: 'generar diagrama de clases'")
            continue
        else:
            continue

        idioma = _detectar_idioma(contenido_modificado)

        messages = _construir_prompt_sync(
            fase_objetivo=fase,
            fase_modificada=fase_modificada,
            contenido_modificado=contenido_modificado,
            contenido_objetivo_actual=contenido_objetivo,
            razones_sync=razones,
            template=template,
            guards=guards,
            idioma=idioma,
        )

        print(f"🔄 Sincronizando {fase.upper()}...")
        resultado: ArtefactoOutput = structured_llm_artefacto.invoke(messages)
        _guardar_artefacto(fase, resultado.contenido)
        resultados[f"{fase}_content"] = resultado.contenido
        resultados[f"{fase}_content_prev"] = contenido_objetivo
        print(f"   ✅ {fase.upper()} sincronizado.")

    if resultados:
        print(f"\n📄 Sincronización completada para: {', '.join(k.replace('_content', '').upper() for k in resultados if not k.endswith('_prev'))}")
        return resultados
    else:
        print("❌ No se sincronizó ningún artefacto.")
        return {"blocked_reason": "No se pudo sincronizar ningún artefacto. Verifica que existan y que sean posteriores a la fase modificada."}


def _extraer_fase_sync(mensaje: str) -> str | None:
    """Extrae la fase objetivo de un mensaje de sincronización."""
    m = mensaje.lower()
    if "todo" in m or "todos" in m:
        return "todo"
    if "discovery" in m or "descubrimiento" in m or "brief" in m:
        return "discovery"
    if "requirements" in m or "requisitos" in m or "req" in m:
        return "requirements"
    if "design" in m or "diseño" in m:
        return "design"
    if "diagram" in m or "diagrama" in m or "clases" in m or "uml" in m:
        return "diagram"
    return None


# ---------------------------------------------------------------------------
# 7. Nodos de respuesta a validación (2-turn flow)
# ---------------------------------------------------------------------------
def nodo_rechazar_validacion(state: State):
    print("❌ Generación rechazada por el usuario. Restaurando versión anterior...")

    fase = state.get("pending_fase")
    if fase:
        prev_content = state.get(f"{fase}_content_prev")
        if prev_content:
            _guardar_artefacto(fase, prev_content)
            print(f"   ✅ {fase.upper()} restaurado a la versión anterior.")
            return {
                f"{fase}_content": prev_content,
                "pending_validation": None,
                "pending_intention": None,
                "pending_fase": None,
                "skip_validation": False,
            }
        else:
            # No había versión anterior, eliminar el artefacto generado
            print(f"   ⚠️ {fase.upper()} eliminado (no había versión anterior).")
            return {
                f"{fase}_content": None,
                f"{fase}_content_prev": None,
                "pending_validation": None,
                "pending_intention": None,
                "pending_fase": None,
                "skip_validation": False,
            }

    return {
        "pending_validation": None,
        "pending_intention": None,
        "pending_fase": None,
        "skip_validation": False,
    }


def nodo_aplicar_validacion(state: State):
    print("⚠️ Aplicando generación a pesar de las inconsistencias detectadas...")
    return {
        "pending_validation": None,
        "pending_intention": None,
        "pending_fase": None,
        "skip_validation": True,
        "fase": state.get("pending_fase"),
    }


def nodo_sincronizar_validacion(state: State):
    print("🔄 Aplicando generación y sincronizando especificaciones afectadas...")
    return {
        "pending_validation": None,
        "pending_intention": None,
        "pending_fase": None,
        "skip_validation": True,
        "fase": state.get("pending_fase"),
        "sync_after_generate": True,
    }


# ---------------------------------------------------------------------------
# 8. Routers
# ---------------------------------------------------------------------------
def router_validador(state: State) -> Literal[
    "nodo_product",
    "nodo_discovery",
    "nodo_requirements",
    "nodo_design",
    "nodo_diagram",
    "nodo_sincronizador",
    "nodo_error",
    "nodo_bloqueado",
    "nodo_rechazar_validacion",
    "nodo_aplicar_validacion",
    "nodo_sincronizar_validacion",
]:
    if state.get("blocked_reason"):
        return "nodo_bloqueado"

    fase = state["fase"]
    if fase == "product":
        return "nodo_product"
    if fase == "discovery":
        return "nodo_discovery"
    if fase == "requirements":
        return "nodo_requirements"
    if fase == "design":
        return "nodo_design"
    if fase == "diagram":
        return "nodo_diagram"
    if fase == "sync":
        return "nodo_sincronizador"
    if fase == "error":
        return "nodo_error"
    if fase == "validation_reject":
        return "nodo_rechazar_validacion"
    if fase == "validation_apply":
        return "nodo_aplicar_validacion"
    if fase == "validation_sync":
        return "nodo_sincronizar_validacion"

    return "nodo_error"


# ---------------------------------------------------------------------------
# 8. Construcción del grafo (FLUJO SIMPLE)
# ---------------------------------------------------------------------------
builder = StateGraph(State)

builder.add_node("nodo_clasificador", nodo_clasificador)
builder.add_node("nodo_validador", nodo_validador)
builder.add_node("nodo_bloqueado", nodo_bloqueado)
builder.add_node("nodo_product", nodo_product)
builder.add_node("nodo_discovery", nodo_discovery)
builder.add_node("nodo_requirements", nodo_requirements)
builder.add_node("nodo_design", nodo_design)
builder.add_node("nodo_diagram", nodo_diagram)
builder.add_node("nodo_sincronizador", nodo_sincronizador)
builder.add_node("nodo_error", nodo_error)
builder.add_node("nodo_rechazar_validacion", nodo_rechazar_validacion)
builder.add_node("nodo_aplicar_validacion", nodo_aplicar_validacion)
builder.add_node("nodo_sincronizar_validacion", nodo_sincronizar_validacion)

# Flujo lineal simple: START -> clasificar -> validar -> generar/sincronizar -> END
builder.add_edge(START, "nodo_clasificador")
builder.add_edge("nodo_clasificador", "nodo_validador")
builder.add_conditional_edges("nodo_validador", router_validador)
builder.add_edge("nodo_product", END)
builder.add_edge("nodo_discovery", END)
builder.add_edge("nodo_requirements", END)
builder.add_edge("nodo_design", END)
builder.add_edge("nodo_diagram", END)
builder.add_edge("nodo_sincronizador", END)
builder.add_edge("nodo_error", END)
builder.add_edge("nodo_bloqueado", END)
builder.add_edge("nodo_rechazar_validacion", END)
builder.add_edge("nodo_aplicar_validacion", END)
builder.add_edge("nodo_sincronizar_validacion", END)

graph = builder.compile()


# ---------------------------------------------------------------------------
# 9. Ejecución por terminal (bucle infinito)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if not os.environ.get("GEMINI_API_KEY"):
        print("⚠️  Error: Debes definir la variable de entorno GEMINI_API_KEY antes de ejecutar.")
        exit(1)

    print("🧠 Flujo SDD con LangGraph + Gemini Flash 2.0 + Vibe Modeling (Diagrama de Clases)")
    print("Fases: PRODUCT → DISCOVERY → REQUIREMENTS → DESIGN → DIAGRAM")
    print("Escribe un mensaje y presiona Enter. Escribe 'salir' para terminar.\n")

    current_state: dict = {
        "messages": [],
        "fase": None,
        "product_content": None,
        "product_content_prev": None,
        "discovery_content": None,
        "discovery_content_prev": None,
        "requirements_content": None,
        "requirements_content_prev": None,
        "design_content": None,
        "design_content_prev": None,
        "diagram_content": None,
        "diagram_content_prev": None,
        "blocked_reason": None,
        "last_active_phase": None,
        "sync_target": None,
        "impacto_analysis": None,
        "pending_validation": None,
        "pending_intention": None,
        "pending_fase": None,
        "skip_validation": False,
        "sync_after_generate": False,
    }

    while True:
        try:
            user_input = input(">> ")
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Saliendo...")
            break

        if user_input.strip().lower() == "salir":
            break

        # Reset de campos transitorios
        current_state["messages"].append(HumanMessage(content=user_input))
        current_state["fase"] = None
        current_state["blocked_reason"] = None

        # Invocar grafo
        result = graph.invoke(current_state)

        # Sincronizar estado persistente
        prev_last_active = current_state.get("last_active_phase")
        prev_pending_intention = current_state.get("pending_intention")
        prev_pending_fase = current_state.get("pending_fase")
        current_state.update(result)
        if "last_active_phase" not in result:
            current_state["last_active_phase"] = prev_last_active
        # Restaurar pending si el resultado los borró (para reprocesamiento)
        if result.get("fase") in ("validation_apply", "validation_sync"):
            if "pending_intention" not in result or result.get("pending_intention") is None:
                current_state["pending_intention"] = prev_pending_intention
            if "pending_fase" not in result or result.get("pending_fase") is None:
                current_state["pending_fase"] = prev_pending_fase

        # Feedback en consola
        if result.get("blocked_reason"):
            msg = f"No se pudo avanzar: {result['blocked_reason']}"
            print(f"\n⛔ {msg}\n")
            current_state["messages"].append(AIMessage(content=msg))
        elif result.get("pending_validation"):
            # Mostrar inconsistencias detectadas post-generación y pedir decisión
            validacion_dict = result.get("pending_validation", {})
            inconsistencias = validacion_dict.get("inconsistencias", [])
            sugerencias = validacion_dict.get("sugerencias", [])
            resumen = validacion_dict.get("resumen", "")

            if inconsistencias:
                print("\n" + "🚨" * 25)
                print("🚨 VALIDACIÓN POST-GENERACIÓN: INCONSISTENCIAS DETECTADAS")
                print("🚨" * 25)
                for i, inc in enumerate(inconsistencias, 1):
                    print(f"\n   {i}. ⚠️  {inc}")
                    if i <= len(sugerencias):
                        print(f"      💡 Sugerencia: {sugerencias[i-1]}")
                if resumen:
                    print(f"\n   📝 Resumen: {resumen}")
                print("\n" + "🚨" * 25)
                print("\n💬 Escribe tu decisión:")
                print("   • 'rechazar' → descarta los cambios y restaura la versión anterior")
                print("   • 'aplicar igual' → conserva los cambios a pesar de las inconsistencias")
                print("   • 'sincronizar' → conserva los cambios y ajusta las otras especificaciones")
            else:
                print("\n✅ VALIDACIÓN POST-GENERACIÓN: Sin inconsistencias estructurales.")
        else:
            fase = result.get("fase")
            if fase == "error":
                msg = "Mensaje no reconocido como parte del flujo SDD."
                print(f"\n❌ {msg}\n")
                current_state["messages"].append(AIMessage(content=msg))
            elif fase in ("product", "discovery", "requirements", "design", "diagram"):
                content = result.get(f"{fase}_content", "")
                print(f"\n📄 Artefacto '{fase.upper()}' generado/refinado.")
                print(f"   📏 Longitud: {len(content)} caracteres.\n")
                current_state["messages"].append(
                    AIMessage(content=f"Artefacto {fase} actualizado/refinado.")
                )
            elif fase == "sync":
                print(f"\n🔄 Sincronización ejecutada.\n")
                current_state["messages"].append(
                    AIMessage(content="Sincronización completada.")
                )
            elif fase in ("validation_reject", "validation_apply", "validation_sync"):
                # El usuario tomó una decisión, procesarla
                if fase == "validation_reject":
                    print("\n❌ Decisión: rechazar. Se restauró la versión anterior.\n")
                    current_state["messages"].append(
                        AIMessage(content="Generación rechazada. Versión anterior restaurada.")
                    )
                elif fase in ("validation_apply", "validation_sync"):
                    # Reproducir la intención original con skip_validation=True
                    pending_intention = result.get("pending_intention") or current_state.get("pending_intention")
                    pending_fase = result.get("pending_fase") or current_state.get("pending_fase")
                    if pending_intention and pending_fase:
                        print(f"\n{'⚠️' if fase == 'validation_apply' else '🔄'} Reprocesando intención: '{pending_intention}'")
                        # Limpiar la decisión anterior del mensaje para que el clasificador vea la intención original
                        current_state["messages"] = current_state["messages"][:-1]
                        current_state["messages"].append(HumanMessage(content=pending_intention))
                        current_state["fase"] = None
                        current_state["blocked_reason"] = None
                        # Forzar reinvocación inmediata sin pedir input nuevo
                        continue
                    else:
                        print("\n❌ Error: no se encontró la intención pendiente.\n")

    print("\n👋 Programa finalizado.")
