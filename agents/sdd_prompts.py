from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage


# ---------------------------------------------------------------------------
# Schemas estrictos
# ---------------------------------------------------------------------------
class FaseOutput(BaseModel):
    """Clasificación obligatoria de la fase de Spec Driven Development."""
    fase: Literal[
        "product", "discovery", "requirements", "design", "diagram",
        "next", "sync", "error",
        "validation_reject", "validation_apply", "validation_sync",
    ] = Field(
        description=(
            "Fase de Spec Driven Development detectada en el mensaje del usuario. "
            "El usuario puede operar en CINCO MODOS: CREACIÓN, REFINAMIENTO, PROGRESIÓN, SINCRONIZACIÓN o RESPUESTA DE VALIDACIÓN.\n\n"
            "=== MODO CREACIÓN (intenciones de alto nivel) ===\n"
            "- product: el usuario expresa una idea de producto, visión de negocio, propuesta de valor "
            "  o quiere definir el QUÉ antes del CÓMO. Es la fase más estratégica y de mayor abstracción. "
            "  Triggers: 'tengo una idea de producto', 'quiero definir el producto', 'product overview', "
            "  'visión del producto', 'para quién es esto', 'qué problema resolvemos', 'propuesta de valor', "
            "  'cuáles son las capacidades del producto', 'use cases', 'quiero empezar desde cero'. "
            "  IMPORTANTE: Si el usuario menciona 'producto', 'visión', 'overview', 'propuesta de valor' o "
            "  habla de la IDEA antes de cualquier detalle técnico, clasifica como PRODUCT.\n"
            "- discovery: el usuario expresa una necesidad de alto nivel, idea de proyecto, "
            "  contexto de negocio o quiere investigar antes de definir nada. "
            "  Ejemplos: 'quiero una aplicación', 'necesito una app', 'tengo una idea', "
            "  'tengo las siguientes necesidades', 'quiero hacer discovery', 'no sé por dónde empezar'. "
            "  NOTA: Si el mensaje es puramente estratégico/visión (sin mencionar tech stack ni funcionalidades), "
            "  prioriza PRODUCT sobre DISCOVERY.\n"
            "- requirements: el usuario pide requisitos, especificaciones, funcionalidades, "
            "  historias de usuario o criterios de aceptación. "
            "  Ejemplos: 'ahora quiero requisitos', 'quiero especificaciones', "
            "  'definir funcionalidades', 'cuáles son los requisitos', 'necesito los req'.\n"
            "- design: el usuario pide diseño, arquitectura, tecnologías, diagramas, "
            "  modelos de datos o stack técnico. "
            "  Ejemplos: 'quiero el diseño', 'cómo lo construimos', 'arquitectura', "
            "  'diseño técnico', 'qué tecnología usar'.\n"
            "- diagram: el usuario pide generar un diagrama de clases, modelo UML, o 'vibe modeling'. "
            "  Es la fase final del flujo SDD. Genera un diagrama de clases en formato JSON compatible con BESSER. "
            "  Triggers: 'generar diagrama de clases', 'diagrama UML', 'modelo de dominio', 'vibe modeling', "
            "  'clases del sistema', 'modelo de clases', 'haz el diagrama', 'crea el diagrama de clases'.\n\n"
            "=== MODO REFINAMIENTO (detecta verbos como agregar, cambiar, modificar, "
            "actualizar, refinar, quitar, incluir, excluir, corregir, amplía, reduce, edita, ajusta, completa) ===\n"
            "Si el usuario menciona una sección específica, clasifica según este mapa:\n"
            "- product: Product Overview, Problem, Value Proposition, Target Use Cases, Core Capabilities, "
            "  Success Criteria, Constraints & Assumptions.\n"
            "- discovery: Brief, Problem, Current State, Desired Outcome, Approach, Scope (In/Out), "
            "  Boundary Candidates, Out of Boundary, Upstream/Downstream, Existing Spec Touchpoints, Constraints.\n"
            "- requirements: Introduction, Boundary Context, Requirements, Requirement N, Objective, "
            "  Acceptance Criteria, EARS.\n"
            "- design: Overview, Goals, Non-Goals, Boundary Commitments, Architecture, File Structure Plan, "
            "  System Flows, Requirements Traceability, Components, Interfaces, Data Models, Error Handling, "
            "  Testing Strategy, Security, Performance, Migration.\n"
            "- diagram: Diagrama de clases, modelo UML, clases, atributos, métodos, relaciones. "
            "  Triggers de refinamiento en diagrama: 'agrega una clase X', 'quita la clase Y', "
            "  'cambia la relación entre A y B', 'agrega atributo Z a la clase W'.\n\n"
            "=== MODO PROGRESIÓN (detecta verbos como continuar, siguiente, adelante, pasemos, listo, vamos) ===\n"
            "- next: el usuario indica que quiere avanzar al siguiente paso del flujo SDD. "
            "  NO sabes cuál es el siguiente paso; solo detecta la intención de progresar. "
            "  Triggers: 'listo, continúa', 'siguiente paso', 'vamos adelante', 'pasemos al siguiente', "
            "  'continuar', 'listo, vamos', 'dale con el siguiente', 'ya está, siguiente'. "
            "  Si el mensaje indica progresión pero también menciona una fase concreta (ej. 'continuar con el diseño'), "
            "  clasifica según la fase mencionada, NO como 'next'.\n\n"
            "=== MODO 5: RESPUESTA DE VALIDACIÓN ===\n"
            "El sistema detectó inconsistencias antes de generar un artefacto y está esperando la decisión del usuario. "
            "Si el estado de sesión indica que hay una 'validación pendiente' (pending_validation), "
            "debes clasificar el mensaje como una de estas tres opciones:\n"
            "- validation_reject: el usuario rechaza la generación. Triggers: 'rechazar', 'cancelar', 'no', "
            "  'olvídalo', 'descartar', 'no quiero', 'mejor no', 'n'.\n"
            "- validation_apply: el usuario acepta generar a pesar de las inconsistencias. Triggers: 'aplicar', "
            "  'aplicar igual', 'continuar', 'sí', 'si', 'adelante', 'ok', 'dale', 'genera', 'hazlo'.\n"
            "- validation_sync: el usuario quiere generar Y sincronizar los artefactos afectados (upstream + downstream). "
            "  Triggers: 'sincronizar', 'sincroniza', 'propagar', 'alinear todo', 'aplicar y sincronizar', "
            "  'sync', 'sincronización', 'propaga los cambios'.\n\n"
            "=== REGLAS DE DESAMBIGUACIÓN ===\n"
            "- 'Product Overview', 'Value Proposition', 'Target Use Cases', 'Core Capabilities' → PRODUCT.\n"
            "- 'Scope' como sección principal (ej. 'agrega al scope', 'quita del scope') SIEMPRE va a DISCOVERY.\n"
            "- 'Approach' o 'stack tecnológico' cuando el usuario habla de decisiones tempranas → DISCOVERY.\n"
            "- 'Boundary Context' o 'Acceptance Criteria' van a REQUIREMENTS.\n"
            "- 'Boundary Commitments' o 'Architecture' van a DESIGN.\n"
            "- 'Diagrama de clases', 'modelo UML', 'clases', 'atributos', 'relaciones' van a DIAGRAM.\n"
            "- 'Boundary' genérico: si es de negocio/módulos → DISCOVERY; si es de contexto funcional → REQUIREMENTS; "
            "  si es de responsabilidad técnica → DESIGN.\n"
            "- Si hay duda entre dos fases, prioriza: Product para visión/estrategia, Discovery para negocio/contexto, "
            "  Requirements para funcionalidades, Design para técnico, Diagram para modelado de clases.\n"
            "- Si hay una validación pendiente en el contexto Y el mensaje se ajusta a rechazar/aplicar/sincronizar, "
            "  SIEMPRE clasifica como validation_reject, validation_apply o validation_sync. "
            "  Esto tiene PRIORIDAD sobre cualquier otra clasificación.\n\n"
            "- error: el mensaje no tiene relación con desarrollo de software o es totalmente incoherente. "
            "  Ejemplos: 'cuéntame un chiste', 'receta de tacos', 'hola cómo estás' (sin más contexto)."
        )
    )


class ArtefactoOutput(BaseModel):
    """Salida estructurada para cualquier artefacto SDD."""
    contenido: str = Field(
        description="Contenido completo del artefacto en formato markdown."
    )


class ImpactoOutput(BaseModel):
    """Análisis de impacto de un cambio en un artefacto sobre los artefactos posteriores."""
    impacta_discovery: bool = Field(
        description="True si el cambio requiere actualizar el artefacto Discovery."
    )
    razon_discovery: str = Field(
        description="Breve explicación de por qué impacta o no a Discovery."
    )
    impacta_requirements: bool = Field(
        description="True si el cambio requiere actualizar el artefacto Requirements."
    )
    razon_requirements: str = Field(
        description="Breve explicación de por qué impacta o no a Requirements."
    )
    impacta_design: bool = Field(
        description="True si el cambio requiere actualizar el artefacto Design."
    )
    razon_design: str = Field(
        description="Breve explicación de por qué impacta o no a Design."
    )
    impacta_diagram: bool = Field(
        default=False,
        description="True si el cambio requiere actualizar el artefacto Diagram (diagrama de clases)."
    )
    razon_diagram: str = Field(
        default="",
        description="Breve explicación de por qué impacta o no a Diagram."
    )
    alertas_upstream: str = Field(
        default="Ninguna",
        description=(
            "Alertas de inconsistencias del artefacto modificado con artefactos ANTERIORES (upstream). "
            "Verifica que el nuevo contenido no contradiga o exceda lo definido en fases anteriores. "
            "Ejemplos: 'El nuevo requisito REQ-005 no está en el Scope In del Discovery', "
            "'El stack propuesto en Design (Laravel) difiere del Approach en Discovery (Django)'. "
            "Si no hay inconsistencias, escribe exactamente 'Ninguna'."
        ),
    )


class ValidacionPreviaOutput(BaseModel):
    """Validación previa de consistencia antes de generar un artefacto."""
    es_valido: bool = Field(
        description="True si la intención del usuario NO introduce inconsistencias con las especificaciones existentes."
    )
    inconsistencias: list[str] = Field(
        default_factory=list,
        description="Lista de inconsistencias detectadas. Vacía si es_valido es True."
    )
    sugerencias: list[str] = Field(
        default_factory=list,
        description="Sugerencias de corrección para cada inconsistencia."
    )
    resumen: str = Field(
        default="",
        description="Breve resumen del análisis de consistencia."
    )


class ValidacionPostGenOutput(BaseModel):
    """Validación post-generación: compara artefacto generado contra otras fases existentes."""
    es_valido: bool = Field(
        description="True si el artefacto generado NO introduce inconsistencias con otras fases existentes."
    )
    inconsistencias: list[str] = Field(
        default_factory=list,
        description="Lista de inconsistencias detectadas entre el artefacto generado y otras fases."
    )
    sugerencias: list[str] = Field(
        default_factory=list,
        description="Sugerencias de corrección para cada inconsistencia."
    )
    resumen: str = Field(
        default="",
        description="Breve resumen del análisis de consistencia inter-fase."
    )
    requiere_rollback: bool = Field(
        default=False,
        description="True si la inconsistencia es tan grave que debería revertirse el cambio automáticamente."
    )


# ---------------------------------------------------------------------------
# 2. System prompt del clasificador (dinámico con contexto de sesión)
# ---------------------------------------------------------------------------
def build_system_prompt_clasificador(
    last_active_phase: str | None,
    has_product: bool,
    has_discovery: bool,
    has_requirements: bool,
    has_design: bool,
    has_diagram: bool = False,
    has_pending_validation: bool = False,
) -> SystemMessage:
    """Construye el system prompt del clasificador incluyendo contexto de sesión."""

    contexto = []
    if last_active_phase:
        contexto.append(f"- Última fase activa: {last_active_phase.upper()}")
    if has_product:
        contexto.append("- Product: ya existe (generado)")
    if has_discovery:
        contexto.append("- Discovery: ya existe (generado)")
    if has_requirements:
        contexto.append("- Requirements: ya existe (generado)")
    if has_design:
        contexto.append("- Design: ya existe (generado)")
    if has_diagram:
        contexto.append("- Diagram: ya existe (generado)")
    if has_pending_validation:
        contexto.append("- VALIDACIÓN PENDIENTE: el sistema detectó inconsistencias y está esperando una decisión del usuario (rechazar/aplicar/sincronizar).")

    contexto_str = "\n".join(contexto) if contexto else "- Ningún artefacto ha sido generado todavía."

    content = (
        "Eres un clasificador especializado en Spec Driven Development (SDD). "
        "Tu única tarea es analizar el mensaje del usuario y devolver SIEMPRE "
        "un JSON con la clave 'fase' cuyo valor sea EXACTAMENTE una de estas opciones: "
        "product, discovery, requirements, design, diagram, next, sync o error.\n\n"
        "=== CONTEXTO DE LA SESIÓN ACTUAL ===\n"
        f"{contexto_str}\n\n"
        "=== REGLA CRÍTICA DE CONTEXTO (FALLBACK) ===\n"
        "1. REGLA DE INICIO OBLIGATORIO: Si NO hay un Product generado todavía (contexto muestra 'Ningún artefacto ha sido generado' o no lista Product), "
        "Y el mensaje del usuario expresa una idea, necesidad, visión o deseo de crear algo (app, sistema, plataforma, producto, herramienta), "
        "ENTONCES clasifica SIEMPRE como PRODUCT. NO como discovery. Product es la puerta de entrada del flujo SDD.\n"
        "2. Si el mensaje del usuario es AMBIGUO o NO menciona explícitamente una fase/sección concreta, "
        "y el mensaje parece un refinamiento (verbos: agregar, cambiar, modificar, quitar, etc.), "
        "DEBES priorizar la ÚLTIMA FASE ACTIVA como destino. "
        "Ejemplo: si la última fase activa fue DISCOVERY y el usuario dice 'cambia el stack a React' "
        "sin mencionar 'design', clasifica como DISCOVERY (la sección Approach del Discovery incluye stack).\n\n"
        "El usuario puede interactuar en CINCO MODOS distintos. Debes detectar en cuál está:\n\n"
        "=== MODO 1: CREACIÓN ===\n"
        "El usuario quiere generar un artefacto completo desde cero.\n"
        "1. product: expresa una idea de producto, visión de negocio, propuesta de valor, "
        "   o quiere definir el QUÉ antes del CÓMO. Es la fase MÁS ESTRATÉGICA y el PUNTO DE INICIO del flujo. "
        "   Triggers principales (ir a PRODUCT si el usuario dice algo como esto y NO especifica otra fase): "
        "   'quiero una aplicación', 'necesito una app', 'quiero una app', 'quiero una plataforma', "
        "   'tengo una idea', 'tengo una idea de producto', 'quiero crear un producto', "
        "   'quiero definir el producto', 'product overview', 'visión del producto', "
        "   'para quién es esto', 'qué problema resolvemos', 'propuesta de valor', "
        "   'capacidades del producto', 'use cases', 'quiero empezar desde cero', "
        "   'quiero un sistema para', 'quiero hacer una app de', 'quiero una herramienta para'. "
        "   IMPORTANTE: Si el usuario dice 'quiero una aplicación para X' o 'necesito una app que haga Y' "
        "   y NO menciona stack técnico, funcionalidades detalladas, ni palabras como 'discovery', 'requisitos', 'diseño', "
        "   ENTONCES clasifica como PRODUCT, NO como discovery. PRODUCT es el punto de entrada por defecto.\n"
        "2. discovery: expresa necesidad de investigar, definir scope, stack o contexto TÉCNICO de negocio. "
        "   SOLO se usa cuando ya existe Product o cuando el usuario menciona explícitamente palabras de Discovery. "
        "   Triggers: 'quiero hacer discovery', 'necesito investigar el proyecto', 'no sé por dónde empezar' (solo si ya hay producto), "
        "   'define el scope', 'cuál es el alcance', 'qué stack usar', 'quiero el brief', 'hazme el brief'. "
        "   NOTA: 'quiero una aplicación' o 'tengo una idea' YA NO van a Discovery; van a Product.\n"
        "3. requirements: pide requisitos, especificaciones, funcionalidades o criterios de aceptación. "
        "   Triggers: 'quiero requisitos', 'quiero especificaciones', 'definir funcionalidades', 'req'.\n"
        "4. design: pide diseño, arquitectura, tecnologías, diagramas o modelo de datos. "
        "   Triggers: 'quiero el diseño', 'cómo lo construimos', 'arquitectura', 'diseño técnico', 'stack'.\n"
        "5. diagram: pide generar un diagrama de clases, modelo UML, o 'vibe modeling'. "
        "   Es la fase FINAL del flujo SDD. Solo disponible cuando ya existe Design. "
        "   Triggers: 'generar diagrama de clases', 'diagrama UML', 'modelo de dominio', 'vibe modeling', "
        "   'clases del sistema', 'modelo de clases', 'haz el diagrama', 'crea el diagrama de clases', "
        "   'quiero el diagrama de clases', 'dame el UML', 'genera el modelo de clases'.\n\n"
        "=== MODO 2: REFINAMIENTO ===\n"
        "El usuario quiere modificar, agregar, quitar, cambiar, corregir, actualizar o refinar "
        "una sección específica de un artefacto ya existente. "
        "Verbos típicos de este modo: agregar, cambiar, modificar, actualizar, refinar, quitar, "
        "incluir, excluir, corregir, amplía, reduce, edita, ajusta, completa, mejora, deja, pon, saca.\n"
        "Cuando detectes este modo, busca la sección que menciona el usuario y clasifica según este mapa:\n\n"
        "PRODUCT (secciones de visión de producto):\n"
        "- Product Overview, Problem, Value Proposition, Target Use Cases, Core Capabilities, "
        "  Success Criteria, Constraints & Assumptions.\n"
        "IMPORTANTE: Product es puramente negocio/visión. NO incluye stack técnico ni funcionalidades detalladas.\n\n"
        "DISCOVERY (secciones de brief/discovery):\n"
        "- Brief, Problem, Current State, Desired Outcome, Approach, Scope (In/Out), "
        "  Boundary Candidates, Out of Boundary, Upstream/Downstream, Existing Spec Touchpoints, Constraints.\n"
        "IMPORTANTE: Approach en Discovery define el stack técnico (React, Next.js, Laravel, etc.). "
        "Scope In/Out define features del MVP (icono de WhatsApp, responsive, mobile, etc.).\n\n"
        "REQUIREMENTS (secciones de requisitos):\n"
        "- Introduction, Boundary Context, Requirements, Requirement N (ej. Requirement 1), "
        "  Objective, Acceptance Criteria, EARS.\n\n"
        "DESIGN (secciones de diseño técnico):\n"
        "- Overview, Goals, Non-Goals, Boundary Commitments, Architecture, File Structure Plan, "
        "  System Flows, Requirements Traceability, Components, Interfaces, Data Models, "
        "  Error Handling, Testing Strategy, Security, Performance, Migration.\n\n"
        "DIAGRAM (refinamiento del diagrama de clases):\n"
        "- Clases, atributos, métodos, relaciones, multiplicidades, herencia, composición. "
        "  Triggers: 'agrega la clase X', 'quita la clase Y', 'cambia la relación entre A y B', "
        "  'agrega atributo Z a W', 'haz que X herede de Y', 'modifica la multiplicidad'.\n\n"
        "=== MODO 3: PROGRESIÓN ===\n"
        "El usuario indica que quiere avanzar al siguiente paso del flujo SDD. "
        "NO intentes adivinar cuál es el siguiente paso; solo detecta la intención de progresar.\n"
        "6. next: el usuario quiere continuar al siguiente paso del flujo. "
        "   Triggers: 'listo, continúa', 'siguiente paso', 'vamos adelante', 'pasemos al siguiente', "
        "   'continuar', 'listo, vamos', 'dale con el siguiente', 'ya está, siguiente', "
        "   'listo, ahora el siguiente', 'continua con lo siguiente'. "
        "   IMPORTANTE: si el mensaje indica progresión PERO también menciona una fase concreta "
        "   (ej. 'continuar con el diseño'), clasifica según la fase mencionada, NO como 'next'.\n\n"
        "=== MODO 4: SINCRONIZACIÓN ===\n"
        "El usuario quiere sincronizar o alinear un artefacto posterior después de detectar una inconsistencia "
        "por un cambio en un artefacto anterior. Esto ocurre cuando el sistema mostró un análisis de impacto.\n"
        "7. sync: el usuario acepta sincronizar un artefacto dependiente para mantener consistencia. "
        "   Triggers: 'sincronizar todo', 'sincronizar discovery', 'sincronizar requirements', 'sincronizar design', "
        "   'actualizar discovery', 'actualizar requirements', 'actualizar design', "
        "   'propagar cambios', 'alinear artefactos', 'sync'. "
        "   IMPORTANTE: Si el usuario menciona 'sincronizar' o 'actualizar' seguido de una fase concreta, "
        "   clasifica como SYNC y anota la fase objetivo en tu razonamiento.\n\n"
        "=== REGLAS DE DESAMBIGUACIÓN OBLIGATORIAS ===\n"
        "- 'Product Overview', 'Value Proposition', 'Target Use Cases', 'Core Capabilities' → PRODUCT.\n"
        "- Si el usuario dice 'en el producto', 'para el product', 'en product', 'del product' → PRODUCT.\n"
        "- 'Scope' como sección principal (ej. 'agrega al scope', 'quita del scope') SIEMPRE va a DISCOVERY.\n"
        "- 'Approach' o 'stack tecnológico' cuando el usuario habla de decisiones tempranas → DISCOVERY.\n"
        "- 'Boundary Context' o 'Acceptance Criteria' van a REQUIREMENTS.\n"
        "- 'Boundary Commitments' o 'Architecture' van a DESIGN.\n"
        "- 'Diagrama de clases', 'modelo UML', 'clases', 'atributos', 'relaciones' → DIAGRAM.\n"
        "- 'Boundary' genérico: si es de negocio/módulos → DISCOVERY; si es de contexto funcional → REQUIREMENTS; "
        "  si es de responsabilidad técnica → DESIGN.\n"
        "- Si hay duda entre dos fases, prioriza: Product para visión/estrategia, Discovery para negocio/contexto, "
        "  Requirements para funcionalidades, Design para técnico, Diagram para modelado de clases.\n"
        "- Si hay duda entre dos fases y NO hay contexto suficiente, usa la REGLA CRÍTICA DE CONTEXTO (FALLBACK).\n\n"
        "=== ERROR ===\n"
        "8. error: el mensaje NO tiene relación con desarrollo de software o es totalmente incoherente. "
        "   Triggers: chistes, recetas, saludos vacíos, clima, etc.\n"
        "   Si el mensaje tiene ALGO que ver con software o proyectos técnicos, NUNCA uses 'error'; "
        "   elige la fase más cercana (product por defecto si es estratégico/visión, discovery si es más técnico). "
        "   Solo usa 'error' cuando sea evidente que el input está fuera de contexto."
    )

    return SystemMessage(content=content)


# ---------------------------------------------------------------------------
# 4. Prompt builders
# ---------------------------------------------------------------------------
def _construir_prompt_generador(
    template: str,
    guards: str,
    user_message: str,
    idioma: str,
    contexto_previo: str | None = None,
    artefacto_actual: str | None = None,
) -> list[SystemMessage | HumanMessage]:
    """Construye el prompt completo para cualquier nodo generador."""

    system_parts = [
        "### REGLA CRÍTICA: NO PLACEHOLDERS, NO TEXTO DE TEMPLATE\n"
        "El template a continuación contiene texto de ejemplo, instrucciones de formato y placeholders como [valor específico], [usuarios objetivo], {{VARIABLE}}, etc.\n"
        "ESTÁ ESTRICTAMENTE PROHIBIDO copiar texto del template o dejar placeholders sin rellenar.\n"
        "Si una sección no aplica al proyecto, OMÍTELA COMPLETAMENTE. NO la dejes con texto genérico, instrucciones del template o placeholders.\n"
        "TODAS las secciones incluidas DEBEN contener contenido específico del proyecto derivado del contexto proporcionado.\n"
        "PROHIBIDO incluir bloques meta del template (Propósito, Enfoque, Advertencia, Purpose, Approach, Warning) en el output final.",
        "\n### INSTRUCCIONES DE PLANTILLA\n" + template,
        "\n### GUARDS Y RESTRICCIONES OBLIGATORIAS\n" + guards,
        f"\n### REGLA DE IDIOMA\n"
        f"El usuario está escribiendo en el idioma detectado: '{idioma}'.\n"
        f"CRÍTICO: Genera TODO el contenido del artefacto en ese EXACTO idioma. "
        f"Los templates son solo guías de ESTRUCTURA, pero el CONTENIDO debe estar completamente en '{idioma}'. "
        f"Si el idioma es español ('es'), todo el artefacto debe estar en español. "
        f"Si es inglés ('en'), todo en inglés. NUNCA mezcles idiomas dentro del artefacto.",
    ]

    if contexto_previo:
        system_parts.append(f"\n### CONTEXTO DE FASES ANTERIORES\n{contexto_previo}")

    if artefacto_actual:
        system_parts.append(
            f"\n### ARTEFACTO ACTUAL (REFINAMIENTO)\n{artefacto_actual}\n"
            "El usuario solicita un cambio. Refina el artefacto anterior manteniendo la "
            "estructura del template y respetando los guards. Devuelve el documento completo actualizado."
        )
    else:
        system_parts.append(
            "Genera el artefacto completo siguiendo la plantilla y respetando TODOS los guards."
        )

    return [
        SystemMessage(content="\n".join(system_parts)),
        HumanMessage(content=user_message),
    ]


def _construir_prompt_sync(
    fase_objetivo: str,
    fase_modificada: str,
    contenido_modificado: str,
    contenido_objetivo_actual: str | None,
    razones_sync: str,
    template: str,
    guards: str,
    idioma: str,
) -> list[SystemMessage | HumanMessage]:
    """Construye el prompt para sincronizar un artefacto con su fuente upstream."""

    system_parts = [
        "### REGLA CRÍTICA: NO PLACEHOLDERS, NO TEXTO DE TEMPLATE\n"
        "El template a continuación contiene texto de ejemplo e instrucciones de formato.\n"
        "ESTÁ ESTRICTAMENTE PROHIBIDO copiar texto del template o dejar placeholders sin rellenar.\n"
        "Si una sección no aplica, OMÍTELA COMPLETAMENTE.\n"
        "TODAS las secciones incluidas DEBEN contener contenido específico del proyecto.",
        "\n### INSTRUCCIONES DE PLANTILLA\n" + template,
        "\n### GUARDS Y RESTRICCIONES OBLIGATORIAS\n" + guards,
        f"\n### REGLA DE IDIOMA\n"
        f"El idioma del proyecto es: '{idioma}'. Genera TODO en este idioma.",
    ]

    sync_instruccion = (
        f"\n### TAREA DE SINCRONIZACIÓN\n"
        f"El artefacto '{fase_modificada.upper()}' fue modificado recientemente. "
        f"Los siguientes cambios requieren que el artefacto '{fase_objetivo.upper()}' se actualice:\n"
        f"{razones_sync}\n\n"
        f"### ARTEFACTO MODIFICADO (fuente de verdad)\n"
        f"{contenido_modificado[:3000]}\n\n"
    )

    if contenido_objetivo_actual:
        sync_instruccion += (
            f"### ARTEFACTO ACTUAL A ACTUALIZAR\n"
            f"{contenido_objetivo_actual[:3000]}\n\n"
            f"Instrucciones: Actualiza el artefacto objetivo para que sea consistente con la fuente. "
            f"Mantén la estructura del template, el formato y las secciones existentes. "
            f"Solo modifica lo necesario para reflejar los cambios de la fuente. "
            f"NO elimines secciones que siguen siendo válidas. "
            f"Devuelve el documento completo actualizado."
        )
    else:
        sync_instruccion += (
            f"El artefacto objetivo no existe todavía. Genera uno nuevo basado en la fuente de verdad."
        )

    system_parts.append(sync_instruccion)

    return [
        SystemMessage(content="\n".join(system_parts)),
        HumanMessage(content=f"Sincroniza {fase_objetivo} con {fase_modificada}"),
    ]


# ---------------------------------------------------------------------------
# 5. Prompt de análisis de impacto
# ---------------------------------------------------------------------------
def build_impact_analysis_prompt(
    fase_modificada: str,
    old_content: str,
    new_content: str,
    product_content: str | None,
    discovery_content: str | None,
    requirements_content: str | None,
    design_content: str | None,
    diagram_content: str | None,
) -> str:
    """Construye el prompt para el análisis de impacto bidireccional."""

    orden = ["product", "discovery", "requirements", "design", "diagram"]
    idx_mod = orden.index(fase_modificada)

    # Upstream context (phases before modified)
    upstream_parts = []
    for i, fase in enumerate(orden):
        if i >= idx_mod:
            break
        content = locals()[f"{fase}_content"]
        if content:
            upstream_parts.append(f"--- {fase.upper()} (UPSTREAM) ---\n{content[:1500]}\n...")
        else:
            upstream_parts.append(f"--- {fase.upper()} (UPSTREAM): No existe todavía ---")

    # Downstream context (phases after modified)
    downstream_parts = []
    for i, fase in enumerate(orden):
        if i <= idx_mod:
            continue
        content = locals()[f"{fase}_content"]
        if content:
            downstream_parts.append(f"--- {fase.upper()} (DOWNSTREAM) ---\n{content[:1500]}\n...")
        else:
            downstream_parts.append(f"--- {fase.upper()} (DOWNSTREAM): No existe todavía ---")

    prompt = (
        "Eres un analista de trazabilidad en Spec Driven Development. "
        "Tu tarea es: 1) Determinar si un cambio en un artefacto requiere actualizar artefactos POSTERIORES (downstream), "
        "y 2) Detectar si el nuevo contenido introduce INCONSISTENCIAS con artefactos ANTERIORES (upstream).\n"
        "Sé AGRESIVO detectando inconsistencias. Es mejor marcar true y sincronizar que dejar una inconsistencia oculta.\n\n"
        f"ARTEFACTO MODIFICADO: {fase_modificada.upper()}\n\n"
        f"CONTENIDO ANTERIOR:\n{old_content[:3000]}\n\n"
        f"CONTENIDO NUEVO:\n{new_content[:3000]}\n\n"
    )

    if upstream_parts:
        prompt += (
            "ARTEFACTOS ANTERIORES (UPSTREAM) - Verifica que el nuevo contenido sea consistente con ellos:\n"
            + "\n\n".join(upstream_parts)
            + "\n\n"
        )

    if downstream_parts:
        prompt += (
            "ARTEFACTOS POSTERIORES (DOWNSTREAM) - Evalúa impacto (SOLO analiza estos, ignora la fase modificada):\n"
            + "\n\n".join(downstream_parts)
            + "\n\n"
        )
    else:
        prompt += "No hay artefactos posteriores. Solo realiza verificación upstream.\n\n"

    prompt += (
        "INSTRUCCIONES:\n"
        "1. Compara el contenido anterior y nuevo del artefacto modificado.\n"
        "2. Determina si los cambios son ESTRUCTURALES o COSMÉTICOS.\n\n"
        "CAMBIOS ESTRUCTURALES (marca impacta_X = true):\n"
        "- Features/capabilities agregadas o eliminadas en Product\n"
        "- Scope In/Out modificado en Discovery (features agregadas/eliminadas del MVP)\n"
        "- Stack tecnológico cambiado en Discovery (Approach: React→Vue, Laravel→Django, etc.)\n"
        "- Requisitos agregados o eliminados en Requirements (nuevo Req ID, req eliminado)\n"
        "- Cambio en Acceptance Criteria que altera la interpretación del requisito\n"
        "- Tecnologías cambiadas en Design (stack, frameworks, bases de datos)\n"
        "- Componentes agregados/eliminados en Design\n"
        "- Cambio en entidades del dominio que requieren actualizar el diagrama de clases\n\n"
        "CAMBIOS COSMÉTICOS (marca impacta_X = false):\n"
        "- Redacción, formato, typos, orden de párrafos\n"
        "- Cambios de estilo o claridad sin cambiar el significado\n"
        "- Correcciones gramaticales\n\n"
        "REGLAS ESPECÍFICAS POR FASE MODIFICADA:\n"
        "- Si Product cambió: Discovery DEBE actualizarse si el nombre, capabilities o use cases cambiaron.\n"
        "- Si Discovery cambió: Requirements DEBE actualizarse si Scope In/Out cambió. "
        "Design DEBE actualizarse si el stack tecnológico (Approach) cambió. "
        "Diagram DEBE actualizarse si cambian las entidades del dominio.\n"
        "- Si Requirements cambió: Design DEBE actualizarse si se agregó/eliminó un requisito o cambió su interpretación. "
        "Diagram DEBE actualizarse si cambian las entidades o relaciones del dominio.\n"
        "- Si Design cambió: Discovery PUEDE necesitar actualización si el stack técnico fue modificado en Design "
        "pero no está reflejado en Discovery Approach. Diagram PUEDE necesitar actualización si cambian componentes o modelos de datos.\n"
        "- Si Diagram cambió: No tiene fases posteriores. Solo verifica upstream (consistencia con Design y Requirements).\n\n"
        "VERIFICACIÓN UPSTREAM (BIDIRECCIONAL) - OBLIGATORIA Y AGRESIVA:\n"
        "- Si el artefacto modificado es Discovery: verifica que sus features/capabilities estén en Product. "
        "Si agregas algo en Discovery que no está en Product, reporta alerta upstream.\n"
        "- Si el artefacto modificado es Requirements: haz DOS verificaciones contra el Discovery:\n"
        "  1. Cada requisito nuevo o modificado DEBE estar dentro del Scope In del Discovery. "
        "     Si hay un requisito que no está en Scope In, reporta alerta upstream.\n"
        "  2. CRÍTICO: Ningún requisito nuevo puede estar en el Scope Out del Discovery (features explícitamente descartadas). "
        "     Si el Discovery dice 'Out: Funcionalidad de subastas' y el nuevo requisito es 'Subasta de carros', "
        "     esto es una INCONSISTENCIA GRAVE. Reporta inmediatamente la alerta upstream con el nombre exacto del item en Scope Out.\n"
        "  3. Verifica que los criterios de aceptación no contradigan el Discovery.\n"
        "- Si el artefacto modificado es Design: verifica que el stack tecnológico coincida con Discovery Approach. "
        "Si Design propone un stack diferente al definido en Discovery, reporta alerta upstream. "
        "También verifica que cada componente/diagrama tenga trazabilidad con un requisito existente.\n"
        "- Si el artefacto modificado es Diagram: verifica que cada clase del diagrama tenga soporte en Requirements o Design. "
        "Si hay una clase en el diagrama que no tiene requisito ni componente asociado, reporta alerta upstream.\n"
        "Si no hay inconsistencias upstream, escribe exactamente 'Ninguna' en alertas_upstream.\n\n"
        "IMPORTANTE: Para artefactos posteriores que NO existen (marcados 'No existe todavía'), "
        "SIEMPRE establece impacta_X = false y razon_X = 'Artefacto no generado todavía, no requiere sincronización'.\n"
        "Sé conservador. Si hay DUDA sobre si un cambio impacta, marca TRUE. "
        "Es mejor sincronizar de más que dejar inconsistencias."
    )

    return prompt


# ---------------------------------------------------------------------------
# 6. Visualización de impacto
# ---------------------------------------------------------------------------
def _mostrar_impacto(impacto: ImpactoOutput, fase_modificada: str):
    """Imprime el análisis de impacto de forma legible para el usuario."""

    print("\n🔍 ANÁLISIS DE IMPACTO EN ARTEFACTOS POSTERIORES:")
    print("─" * 60)

    orden = ["product", "discovery", "requirements", "design", "diagram"]
    idx_mod = orden.index(fase_modificada)

    filas = []
    for fase in orden[idx_mod + 1 :]:
        impacta = getattr(impacto, f"impacta_{fase}")
        razon = getattr(impacto, f"razon_{fase}")
        if impacta:
            filas.append((fase.capitalize(), "🔴 REQUIERE SINCRONIZACIÓN", razon))
        else:
            filas.append((fase.capitalize(), "✅ Sin cambios necesarios", razon))

    for artefacto, estado, razon in filas:
        print(f"\n📋 {artefacto}: {estado}")
        print(f"   💡 {razon}")

    necesita_sync = any(
        getattr(impacto, f"impacta_{fase}") for fase in orden[idx_mod + 1 :]
    )
    if necesita_sync:
        print(
            "\n💬 Para sincronizar, escribe: 'sincronizar todo' o 'sincronizar discovery' etc."
        )
    else:
        print("\n✅ Todos los artefactos posteriores siguen consistentes.")

    # Upstream alerts
    alertas = getattr(impacto, "alertas_upstream", None)
    if alertas and alertas != "Ninguna":
        print(f"\n🚨 {'='*50}")
        print(f"🚨 ALERTA CRÍTICA DE CONSISTENCIA CON FASES ANTERIORES:")
        print(f"🚨 {'='*50}")
        print(f"   {alertas}")
        print(f"\n💡 ¿Qué hacer? Revisa si este cambio debe propagarse upstream")
        print(f"   (por ejemplo, mover 'Scope Out' a 'Scope In' en Discovery)")
        print(f"   o si el requisito debe ser descartado para mantener alineación.")
        print(f"🚨 {'='*50}")

    print("─" * 60)


# ---------------------------------------------------------------------------
# 7. Prompt de validación previa (Approval Gate)
# ---------------------------------------------------------------------------
def build_validation_prompt(
    fase_destino: str,
    intencion_usuario: str,
    product_content: str | None,
    discovery_content: str | None,
    requirements_content: str | None,
    design_content: str | None,
    diagram_content: str | None,
) -> str:
    """Construye el prompt para validar consistencia previa a la generación."""

    # NUNCA incluir la fase destino como artefacto a comparar.
    # Solo incluir otras fases (upstream y downstream) que YA existen.
    artefactos = []
    if product_content and fase_destino != "product":
        artefactos.append(f"--- PRODUCT (UPSTREAM) ---\n{product_content[:2000]}\n...")
    if discovery_content and fase_destino != "discovery":
        artefactos.append(f"--- DISCOVERY (UPSTREAM/DOWNSTREAM) ---\n{discovery_content[:2000]}\n...")
    if requirements_content and fase_destino != "requirements":
        artefactos.append(f"--- REQUIREMENTS (UPSTREAM/DOWNSTREAM) ---\n{requirements_content[:2000]}\n...")
    if design_content and fase_destino != "design":
        artefactos.append(f"--- DESIGN (DOWNSTREAM) ---\n{design_content[:2000]}\n...")
    if diagram_content and fase_destino != "diagram":
        artefactos.append(f"--- DIAGRAM (DOWNSTREAM) ---\n{diagram_content[:2000]}\n...")

    prompt = (
        "Eres un analista de trazabilidad en Spec Driven Development. "
        "Tu tarea es VALIDAR la intención del usuario ANTES de que se genere cualquier artefacto. "
        "Detecta si la intención introduciría INCONSISTENCIAS con las especificaciones YA EXISTENTES en OTRAS FASES.\n\n"
        "IMPORTANTE: NO compares la intención contra la fase que el usuario está modificando. "
        "Solo compara contra otras fases que ya existen. Es NORMAL que al modificar una fase se cambie algo "
        "que antes decía otra cosa; eso NO es inconsistencia. La inconsistencia solo ocurre cuando una fase "
        "contradice otra fase DIFERENTE.\n\n"
        f"FASE QUE SE ESTÁ MODIFICANDO: {fase_destino.upper()}\n"
        f"INTENCIÓN DEL USUARIO: {intencion_usuario}\n\n"
    )

    if artefactos:
        prompt += "OTRAS FASES EXISTENTES (solo estas pueden tener inconsistencias):\n" + "\n\n".join(artefactos) + "\n\n"
    else:
        prompt += "No hay otras fases existentes todavía. No se puede verificar consistencia inter-fase.\n\n"

    prompt += (
        "REGLAS DE CONSISTENCIA (verifica SOLO contradicciones ENTRE FASES DIFERENTES):\n"
        "\n"
        "CAMBIOS QUE NO SON INCONSISTENCIAS (reporta como válido):\n"
        "- Modificar el Scope In/Out de Discovery (eso es refinamiento, no inconsistencia).\n"
        "- Cambiar el Approach/Stack de Discovery (eso es decisión de diseño temprana).\n"
        "- Cambiar el nombre del producto, redacción, typos, o ajustes cosméticos en cualquier fase.\n"
        "- Agregar o quitar requisitos, features, capabilities (eso es evolución normal del proyecto).\n"
        "- Cualquier modificación dentro de una misma fase que no afecte otras fases.\n"
        "\n"
        "CAMBIOS QUE SÍ SON INCONSISTENCIAS (reporta como inválido):\n"
        "1. Si modifico REQUIREMENTS: un requisito nuevo que no está en Discovery Scope In.\n"
        "2. Si modifico REQUIREMENTS: un requisito que contradice Discovery Scope Out (ej: pido 'subastas' pero Discovery Scope Out dice 'Funcionalidad de subastas').\n"
        "3. Si modifico DESIGN: stack tecnológico que difiere del Discovery Approach.\n"
        "4. Si modifico DESIGN: componente que no tiene trazabilidad con ningún Requirement existente.\n"
        "5. Si modifico DISCOVERY: agregar una feature al Scope In que NO está reflejada en Product Core Capabilities o Target Use Cases.\n"
        "6. Si modifico PRODUCT: agregar una capability que contradice explícitamente algo en Discovery (muy raro).\n"
        "7. Si modifico cualquier fase: introducir algo que contradiga explícitamente una fase posterior ya generada (ej: quitar una feature de Discovery que ya tiene Requirements escritos).\n"
        "8. Si modifico DIAGRAM: agregar una clase que no tiene soporte en Requirements o Design.\n\n"
        "Sé MODERADO detectando inconsistencias. Solo reporta cuando hay una contradicción REAL entre DOS FASES DIFERENTES. "
        "Un refinamiento o evolución dentro del flujo normal NO es inconsistencia.\n\n"
        "Responde en JSON con la estructura exacta:\n"
        '  "es_valido": true/false,\n'
        '  "inconsistencias": ["descripción 1", "descripción 2"],\n'
        '  "sugerencias": ["sugerencia 1", "sugerencia 2"],\n'
        '  "resumen": "Breve resumen del análisis"'
    )

    return prompt


# ---------------------------------------------------------------------------
# 7b. Prompt de validación POST-GENERACIÓN (nodo validador robusto)
# ---------------------------------------------------------------------------
def build_post_validation_prompt(
    fase_modificada: str,
    old_content: str | None,
    new_content: str,
    product_content: str | None,
    discovery_content: str | None,
    requirements_content: str | None,
    design_content: str | None,
    diagram_content: str | None,
) -> str:
    """Construye el prompt para validar un artefacto YA GENERADO contra otras fases existentes."""

    # NUNCA incluir la fase modificada como referencia
    artefactos = []
    if product_content and fase_modificada != "product":
        artefactos.append(f"--- PRODUCT (EXISTENTE) ---\n{product_content[:2000]}\n...")
    if discovery_content and fase_modificada != "discovery":
        artefactos.append(f"--- DISCOVERY (EXISTENTE) ---\n{discovery_content[:2000]}\n...")
    if requirements_content and fase_modificada != "requirements":
        artefactos.append(f"--- REQUIREMENTS (EXISTENTE) ---\n{requirements_content[:2000]}\n...")
    if design_content and fase_modificada != "design":
        artefactos.append(f"--- DESIGN (EXISTENTE) ---\n{design_content[:2000]}\n...")
    if diagram_content and fase_modificada != "diagram":
        artefactos.append(f"--- DIAGRAM (EXISTENTE) ---\n{diagram_content[:2000]}\n...")

    # Calcular diff simple para mostrar qué cambió
    diff_section = ""
    if old_content:
        diff_section = (
            f"CONTENIDO ANTERIOR DE {fase_modificada.upper()}:\n"
            f"{old_content[:2000]}\n\n"
            f"CONTENIDO NUEVO DE {fase_modificada.upper()}:\n"
            f"{new_content[:2000]}\n\n"
            "INSTRUCCIÓN: Analiza QUÉ CAMBIÓ entre la versión anterior y la nueva. "
            "Específicamente, identifica features, capabilities, requisitos, componentes o tecnologías "
            "que se AGREGARON, ELIMINARON o MODIFICARON.\n\n"
        )
    else:
        diff_section = (
            f"CONTENIDO NUEVO DE {fase_modificada.upper()} (primera vez que se genera):\n"
            f"{new_content[:2000]}\n\n"
        )

    prompt = (
        "Eres un analista de trazabilidad en Spec Driven Development (SDD).\n\n"
        "Tu tarea es VALIDAR un artefacto YA GENERADO contra especificaciones de OTRAS FASES.\n"
        "NO compares el artefacto consigo mismo. Solo detecta inconsistencias ENTRE FASES DIFERENTES.\n\n"
        f"FASE MODIFICADA: {fase_modificada.upper()}\n\n"
        f"{diff_section}"
    )

    if artefactos:
        prompt += "OTRAS FASES EXISTENTES (contra las que validar):\n" + "\n\n".join(artefactos) + "\n\n"
    else:
        prompt += "No hay otras fases existentes para comparar.\n\n"

    prompt += (
        "INSTRUCCIONES DE VALIDACIÓN INTER-FASE (sé AGRESIVO):\n"
        "\n"
        "PASO 1 - Identificar el CAMBIO:\n"
        "Primero, determina EXACTAMENTE qué cambió en la fase modificada comparando anterior vs nuevo.\n"
        "Pregúntate: ¿Se agregó alguna feature, capability, requisito, componente o tecnología nueva?\n"
        "Pregúntate: ¿Se eliminó algo que antes existía?\n"
        "Pregúntate: ¿Se modificó el alcance, stack o funcionalidad?\n\n"
        "PASO 2 - Verificar UPSTREAM (fases anteriores):\n"
        "Si la fase modificada introdujo algo NUEVO, verifica que esté soportado por fases anteriores.\n"
        "Si la fase modificada eliminó algo, verifica que no rompa fases posteriores.\n\n"
        "=== REGLA CRÍTICA 1: Discovery vs Product (UPSTREAM) ===\n"
        "Si la fase modificada es DISCOVERY y se agregó algo nuevo:\n"
        "- Cada feature agregada al Scope In DEBE estar soportada por Product (Core Capabilities o Target Use Cases).\n"
        "- Si Product menciona solo 'carros' y Discovery ahora agrega 'motos' → INCONSISTENCIA GRAVE.\n"
        "- Si Product no menciona 'multi-idioma' y Discovery lo agrega → INCONSISTENCIA (a menos que esté implícito).\n"
        "- Si Product no menciona 'administradores' y Discovery agrega 'panel de admin' → INCONSISTENCIA.\n"
        "- Lee TODO el Product Overview y Core Capabilities. Si algo nuevo en Discovery no está allí → reporta.\n\n"
        "=== REGLA CRÍTICA 2: Requirements vs Discovery (UPSTREAM) ===\n"
        "Si la fase modificada es REQUIREMENTS:\n"
        "- Identifica cada requisito NUEVO comparando contra la versión anterior.\n"
        "- Cada requisito nuevo DEBE estar soportado por una feature en Discovery Scope In.\n"
        "- CRÍTICO: Ningún requisito nuevo puede contradecir Discovery Scope Out.\n"
        "  Si Discovery Scope Out dice 'Funcionalidad de subastas' y el nuevo requisito habla de 'subasta', 'puja', 'oferta' o 'remate' → INCONSISTENCIA GRAVE.\n"
        "  Si Discovery Scope Out dice 'Pasarela de pagos' y el nuevo requisito habla de 'pago', 'checkout', 'transacción' → INCONSISTENCIA GRAVE.\n"
        "- Lee TODO el Scope Out del Discovery y verifica que ningún requisito nuevo lo contradiga.\n\n"
        "=== REGLA CRÍTICA 3: Design vs Discovery + Requirements (UPSTREAM) ===\n"
        "Si la fase modificada es DESIGN:\n"
        "- Identifica si el stack tecnológico cambió comparando contra la versión anterior.\n"
        "- El stack (frameworks, lenguajes, bases de datos) DEBE coincidir con Discovery Approach.\n"
        "- Cada componente o módulo nuevo DEBE tener trazabilidad con al menos un Requirement existente.\n"
        "- Si se agregó un componente que no tiene requisito asociado → INCONSISTENCIA.\n\n"
        "=== REGLA CRÍTICA 4: Diagram vs Design + Requirements (UPSTREAM) ===\n"
        "Si la fase modificada es DIAGRAM:\n"
        "- Cada clase del diagrama DEBE tener soporte en Requirements (una entidad del dominio) o en Design (un componente/modelo de datos).\n"
        "- Si hay una clase en el diagrama que no aparece en ningún requisito ni en Design → INCONSISTENCIA.\n"
        "- Las relaciones del diagrama (herencia, composición) DEBEN estar justificadas por los requisitos o el diseño.\n\n"
        "=== REGLA CRÍTICA 5: Product vs Fases Posteriores (DOWNSTREAM) ===\n"
        "Si la fase modificada es PRODUCT:\n"
        "- Identifica si se eliminó alguna capability comparando contra la versión anterior.\n"
        "- Una capability eliminada que YA tiene Requirements escritos → INCONSISTENCIA.\n"
        "- Una capability nueva que no está en Discovery → NO es inconsistencia (es evolución).\n\n"
        "=== REGLA CRÍTICA 6: Cambios que rompen trazabilidad ===\n"
        "Si cualquier fase elimina o modifica algo que otras fases ya dependen de ello:\n"
        "- Discovery quita una feature del Scope In que ya tiene Requirements → INCONSISTENCIA.\n"
        "- Discovery cambia el stack en Approach que ya está reflejado en Design → INCONSISTENCIA.\n"
        "- Requirements elimina un requisito que ya tiene componentes en Design → INCONSISTENCIA.\n"
        "- Design elimina un componente/modelo que ya está en Diagram → INCONSISTENCIA.\n\n"
        "REPORTE:\n"
        "- 'es_valido': true SOLO si no hay ninguna inconsistencia estructural.\n"
        "- 'es_valido': false si hay CUALQUIER inconsistencia, por mínima que parezca.\n"
        "- 'requiere_rollback': true SOLO si la inconsistencia es grave (Scope Out violado, stack incompatible, feature no soportada).\n"
        "- Incluye la descripción EXACTA de qué se contradice y dónde.\n\n"
        "Responde en JSON con la estructura exacta:\n"
        '  "es_valido": true/false,\n'
        '  "inconsistencias": ["descripción detallada 1", "descripción detallada 2"],\n'
        '  "sugerencias": ["sugerencia 1", "sugerencia 2"],\n'
        '  "resumen": "Breve resumen de las inconsistencias encontradas",\n'
        '  "requiere_rollback": true/false'
    )

    return prompt


def _mostrar_validacion_previa(validacion: ValidacionPreviaOutput):
    """Imprime el resultado de la validación previa."""
    if validacion.es_valido:
        print("\n✅ VALIDACIÓN PREVIA: Todas las especificaciones mantienen consistencia.")
        return True

    print("\n" + "🚨" * 25)
    print("🚨 VALIDACIÓN PREVIA: INCONSISTENCIAS DETECTADAS")
    print("🚨" * 25)

    for i, inc in enumerate(validacion.inconsistencias, 1):
        print(f"\n   {i}. ⚠️  {inc}")
        if i <= len(validacion.sugerencias):
            print(f"      💡 Sugerencia: {validacion.sugerencias[i-1]}")

    print(f"\n   📝 Resumen: {validacion.resumen}")
    print("\n" + "🚨" * 25)

    return False
