"""
SDD WebSocket Server — bridges the React frontend to the LangGraph workflow.

Run:  uvicorn sdd_server:app --host 0.0.0.0 --port 8765 --reload
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import shutil
import traceback
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# LangGraph imports (lazy so the server starts even if deps are missing)
# ---------------------------------------------------------------------------
_graph = None
_State = None

# The actual agents/ directory (never changes)
_AGENTS_DIR = pathlib.Path(__file__).parent


def _get_graph():
    global _graph, _State
    if _graph is None:
        from sdd_workflow import graph as g, State as S
        _graph = g
        _State = S
    return _graph, _State


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="BESSER SDD Agent Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory session store
# ---------------------------------------------------------------------------
_DEFAULT_OUTPUT_DIR = str(_AGENTS_DIR / "output")
PHASE_ORDER = ["product", "discovery", "requirements", "design", "diagram"]


def _make_empty_state() -> Dict[str, Any]:
    return {
        "messages": [],
        "fase": None,
        "product_content": None, "product_content_prev": None,
        "discovery_content": None, "discovery_content_prev": None,
        "requirements_content": None, "requirements_content_prev": None,
        "design_content": None, "design_content_prev": None,
        "diagram_content": None, "diagram_content_prev": None,
        "blocked_reason": None, "last_active_phase": None,
        "sync_target": None, "impacto_analysis": None,
        "pending_validation": None, "pending_intention": None,
        "pending_fase": None, "skip_validation": False,
        "sync_after_generate": False,
    }


def _list_output_files(output_dir: str) -> List[Dict[str, str]]:
    base = pathlib.Path(output_dir)
    if not base.exists():
        return []
    files = []
    for p in sorted(base.rglob("*")):
        if p.is_file():
            rel = str(p.relative_to(base)).replace("\\", "/")
            files.append({"path": rel, "name": p.name, "ext": p.suffix, "size": p.stat().st_size})
    return files


def _initialize_project_dir(output_dir: str) -> dict:
    """
    Initialize a project directory:
    1. Create the output dir.
    2. Copy 'especificaciones' templates from agents/ to output_dir's PARENT
       so _load_spec() finds them when SCRIPT_DIR is pointed there.
    """
    out_path = pathlib.Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    project_root = out_path.parent
    src_specs = _AGENTS_DIR / "especificaciones"
    dst_specs = project_root / "especificaciones"

    copied_files = []
    if src_specs.exists() and not dst_specs.exists():
        shutil.copytree(str(src_specs), str(dst_specs))
        for f in dst_specs.rglob("*"):
            if f.is_file():
                copied_files.append(str(f.relative_to(project_root)))
        print(f"   📋 Copied {len(copied_files)} template files to {dst_specs}")
    elif src_specs.exists() and dst_specs.exists():
        for src_file in src_specs.rglob("*"):
            if src_file.is_file():
                rel = src_file.relative_to(src_specs)
                dst_file = dst_specs / rel
                if not dst_file.exists():
                    dst_file.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(src_file), str(dst_file))
                    copied_files.append(str(rel))
        if copied_files:
            print(f"   📋 Copied {len(copied_files)} missing template files")

    return {"initialized": True, "outputDir": str(out_path), "copiedFiles": copied_files}


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------
class FileWriteBody(BaseModel):
    content: str


class ListModelsBody(BaseModel):
    provider: str
    apiKey: str


@app.get("/api/sdd/files")
async def api_list_files(dir: str = _DEFAULT_OUTPUT_DIR):
    return JSONResponse(_list_output_files(dir))


@app.get("/api/sdd/files/{file_path:path}")
async def api_read_file(file_path: str, dir: str = _DEFAULT_OUTPUT_DIR):
    full = pathlib.Path(dir) / file_path
    if not full.exists() or not full.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)
    return JSONResponse({"path": file_path, "content": full.read_text(encoding="utf-8")})


@app.put("/api/sdd/files/{file_path:path}")
async def api_write_file(file_path: str, body: FileWriteBody, dir: str = _DEFAULT_OUTPUT_DIR):
    full = pathlib.Path(dir) / file_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(body.content, encoding="utf-8")
    return JSONResponse({"ok": True, "path": file_path})


@app.post("/api/sdd/list-models")
async def api_list_models(body: ListModelsBody):
    """Fetch available models for the given provider and API key."""
    try:
        models: list[dict] = []
        if body.provider == "gemini":
            # Google AI Studio - list models endpoint
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={body.apiKey}"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            for m in data.get("models", []):
                name = m.get("name", "")  # e.g. "models/gemini-2.5-flash"
                model_id = name.replace("models/", "")
                display = m.get("displayName", model_id)
                # Only include generateContent-capable models
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    models.append({"id": model_id, "name": display})
        elif body.provider == "openai":
            url = "https://api.openai.com/v1/models"
            headers = {"Authorization": f"Bearer {body.apiKey}"}
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            for m in data.get("data", []):
                mid = m.get("id", "")
                # Filter for chat-capable models
                if any(k in mid for k in ["gpt-4", "gpt-3.5", "o1", "o3", "o4"]):
                    models.append({"id": mid, "name": mid})
        # Sort alphabetically
        models.sort(key=lambda x: x["name"])
        return JSONResponse({"models": models})
    except httpx.HTTPStatusError as e:
        return JSONResponse({"error": f"API error: {e.response.status_code}", "models": []}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e), "models": []}, status_code=500)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------
@app.websocket("/ws/sdd")
async def sdd_websocket(ws: WebSocket):
    await ws.accept()
    state = _make_empty_state()
    output_dir = _DEFAULT_OUTPUT_DIR
    config = {"api_key": "", "model": "gemini-2.5-flash", "provider": "gemini"}

    async def send(msg: dict):
        await ws.send_json(msg)

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type", "")

            # --- Config ---
            if msg_type == "config":
                if "apiKey" in data:
                    config["api_key"] = data["apiKey"]
                    os.environ["GOOGLE_API_KEY"] = data["apiKey"]
                if "model" in data:
                    config["model"] = data["model"]
                if "provider" in data:
                    config["provider"] = data["provider"]
                if "outputDir" in data:
                    output_dir = data["outputDir"]
                    _initialize_project_dir(output_dir)
                    print(f"   📁 Output dir: {output_dir}")
                await send({"type": "config_ack", "config": config, "outputDir": output_dir})
                continue

            if msg_type == "reset":
                state = _make_empty_state()
                await send({"type": "reset_ack"})
                continue

            if msg_type == "list_files":
                await send({"type": "files", "files": _list_output_files(output_dir)})
                continue

            if msg_type == "read_file":
                fp = data.get("path", "")
                full = pathlib.Path(output_dir) / fp
                if full.exists() and full.is_file():
                    await send({"type": "file_content", "path": fp, "content": full.read_text(encoding="utf-8")})
                else:
                    await send({"type": "error", "message": f"File not found: {fp}"})
                continue

            if msg_type == "write_file":
                fp = data.get("path", "")
                full = pathlib.Path(output_dir) / fp
                full.parent.mkdir(parents=True, exist_ok=True)
                full.write_text(data.get("content", ""), encoding="utf-8")
                await send({"type": "file_saved", "path": fp})
                continue

            # --- Chat message ---
            if msg_type == "message":
                user_text = data.get("content", "").strip()
                if not user_text:
                    await send({"type": "error", "message": "Empty message"})
                    continue

                await send({"type": "status", "status": "processing", "message": "Clasificando intención..."})

                try:
                    import sdd_workflow as sw
                    from langchain_google_genai import ChatGoogleGenerativeAI
                    from langchain_core.messages import HumanMessage, AIMessage

                    # Update LLM if API key set
                    if config["api_key"]:
                        provider = config.get("provider", "gemini")
                        if provider == "openai":
                            from langchain_openai import ChatOpenAI
                            os.environ["OPENAI_API_KEY"] = config["api_key"]
                            sw.llm = ChatOpenAI(
                                model=config["model"], temperature=0.2,
                                api_key=config["api_key"],
                            )
                        else:
                            os.environ["GOOGLE_API_KEY"] = config["api_key"]
                            sw.llm = ChatGoogleGenerativeAI(
                                model=config["model"], temperature=0.2,
                                google_api_key=config["api_key"],
                            )
                        sw.structured_llm_fase = sw.llm.with_structured_output(sw.FaseOutput)
                        sw.structured_llm_artefacto = sw.llm.with_structured_output(sw.ArtefactoOutput)
                        sw.structured_llm_impacto = sw.llm.with_structured_output(sw.ImpactoOutput)
                        sw.structured_llm_validacion = sw.llm.with_structured_output(sw.ValidacionPreviaOutput)
                        sw.structured_llm_post_validacion = sw.llm.with_structured_output(sw.ValidacionPostGenOutput)
                        sw.structured_llm_diagram = sw.llm.with_structured_output(sw.SystemClassSpec)

                    # Point SCRIPT_DIR so _load_spec() finds especificaciones/
                    if output_dir != _DEFAULT_OUTPUT_DIR:
                        sw.SCRIPT_DIR = pathlib.Path(output_dir).parent
                    else:
                        sw.SCRIPT_DIR = _AGENTS_DIR

                    # Patch save functions to write to our output dir
                    _out = pathlib.Path(output_dir)
                    _out.mkdir(parents=True, exist_ok=True)

                    def _custom_guardar(nombre, contenido, _dir=_out):
                        path = _dir / f"{nombre}.md"
                        path.write_text(contenido, encoding="utf-8")
                        print(f"   💾 Guardado: {path}")
                    sw._guardar_artefacto = _custom_guardar

                    def _custom_guardar_json(contenido, _dir=_out):
                        path = _dir / "class-diagram.json"
                        path.write_text(contenido, encoding="utf-8")
                        print(f"   💾 Diagrama: {path}")
                    sw._guardar_diagrama_json = _custom_guardar_json

                    graph, State = _get_graph()
                    state["messages"].append(HumanMessage(content=user_text))
                    state["fase"] = None
                    state["blocked_reason"] = None

                    result = await asyncio.to_thread(graph.invoke, state)

                    # Sync state
                    prev_last = state.get("last_active_phase")
                    prev_pi = state.get("pending_intention")
                    prev_pf = state.get("pending_fase")
                    state.update(result)
                    if "last_active_phase" not in result:
                        state["last_active_phase"] = prev_last
                    if result.get("fase") in ("validation_apply", "validation_sync"):
                        if not result.get("pending_intention"):
                            state["pending_intention"] = prev_pi
                        if not result.get("pending_fase"):
                            state["pending_fase"] = prev_pf

                    fase = result.get("fase", "")
                    response: Dict[str, Any] = {
                        "type": "response", "fase": fase,
                        "lastActivePhase": state.get("last_active_phase"),
                        "blockedReason": result.get("blocked_reason"),
                        "pendingValidation": result.get("pending_validation"),
                        "impactoAnalysis": result.get("impacto_analysis"),
                    }

                    phases_status = {}
                    for p in PHASE_ORDER:
                        phases_status[p] = {
                            "completed": state.get(f"{p}_content") is not None,
                            "contentLength": len(state.get(f"{p}_content") or ""),
                        }
                    response["phasesStatus"] = phases_status

                    if fase in PHASE_ORDER:
                        response["artifactContent"] = state.get(f"{fase}_content", "")
                        response["artifactName"] = fase
                        msg = f"Artefacto {fase.upper()} generado/refinado correctamente."
                        state["messages"].append(AIMessage(content=msg))
                        response["assistantMessage"] = msg
                    elif fase == "error":
                        msg = "Mensaje no reconocido como parte del flujo SDD."
                        state["messages"].append(AIMessage(content=msg))
                        response["assistantMessage"] = msg
                    elif result.get("blocked_reason"):
                        msg = f"No se pudo avanzar: {result['blocked_reason']}"
                        state["messages"].append(AIMessage(content=msg))
                        response["assistantMessage"] = msg
                    elif result.get("pending_validation"):
                        v = result["pending_validation"]
                        msg = (
                            "⚠️ Se detectaron inconsistencias post-generación.\n\n"
                            + "\n".join(f"• {i}" for i in v.get("inconsistencias", []))
                            + ("\n\n💡 Sugerencias:\n" + "\n".join(f"• {s}" for s in v.get("sugerencias", [])) if v.get("sugerencias") else "")
                            + (f"\n\n📝 {v.get('resumen', '')}" if v.get("resumen") else "")
                            + "\n\n¿Qué deseas hacer? **rechazar**, **aplicar igual**, o **sincronizar**."
                        )
                        state["messages"].append(AIMessage(content=msg))
                        response["assistantMessage"] = msg
                    elif fase == "sync":
                        msg = "Sincronización completada."
                        state["messages"].append(AIMessage(content=msg))
                        response["assistantMessage"] = msg
                    elif fase == "validation_reject":
                        msg = "Generación rechazada. Versión anterior restaurada."
                        state["messages"].append(AIMessage(content=msg))
                        response["assistantMessage"] = msg
                    elif fase in ("validation_apply", "validation_sync"):
                        pi = state.get("pending_intention")
                        pf = state.get("pending_fase")
                        if pi and pf:
                            state["messages"] = state["messages"][:-1]
                            state["messages"].append(HumanMessage(content=pi))
                            state["fase"] = None
                            state["blocked_reason"] = None
                            r2 = await asyncio.to_thread(graph.invoke, state)
                            state.update(r2)
                            f2 = r2.get("fase", "")
                            if f2 in PHASE_ORDER:
                                response["artifactContent"] = state.get(f"{f2}_content", "")
                                response["artifactName"] = f2
                                response["fase"] = f2
                                msg = f"Artefacto {f2.upper()} generado/refinado correctamente."
                                state["messages"].append(AIMessage(content=msg))
                                response["assistantMessage"] = msg
                                for p in PHASE_ORDER:
                                    phases_status[p] = {"completed": state.get(f"{p}_content") is not None, "contentLength": len(state.get(f"{p}_content") or "")}
                                response["phasesStatus"] = phases_status
                        else:
                            msg = "Error: no se encontró la intención pendiente."
                            state["messages"].append(AIMessage(content=msg))
                            response["assistantMessage"] = msg
                    else:
                        response["assistantMessage"] = "Procesado."

                    # Diagram JSON
                    dp = pathlib.Path(output_dir) / "class-diagram.json"
                    if dp.exists() and fase == "diagram":
                        try:
                            response["diagramJson"] = json.loads(dp.read_text(encoding="utf-8"))
                        except Exception:
                            pass

                    response["files"] = _list_output_files(output_dir)
                    await send(response)

                except Exception as exc:
                    tb = traceback.format_exc()
                    print(f"Error: {exc}\n{tb}")
                    await send({"type": "error", "message": f"Error: {str(exc)}", "traceback": tb})

    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as exc:
        print(f"WebSocket error: {exc}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("sdd_server:app", host="0.0.0.0", port=8765, reload=True)
