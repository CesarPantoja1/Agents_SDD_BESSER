# Guards para Discovery

## Reglas de contenido
- El Approach DEBE definir el stack técnico completo (frontend, backend, base de datos, framework principal).
- El Scope In DEBE listar features concretas del MVP. Sé selectivo: máximo 7 features principales.
- El Scope Out DEBE listar features explícitamente excluidas para prevenir scope creep.
- NO inventes features que el usuario no mencionó explícitamente.
- Boundary Candidates DEBEN reflejar los dominios / módulos derivados del Scope In.

## Reglas de trazabilidad futura
- Cada item de Scope In DEBE ser una feature que luego generará requisitos en Requirements.
- Usa nombres claros y consistentes en Scope In, porque Requirements los referenciará.
- El Approach es la única sección del Discovery donde se permiten decisiones técnicas (stack). Todo lo demás es negocio/contexto.

## Regla de idioma
- Detecta el idioma del mensaje del usuario y genera TODO el artefacto en ese mismo idioma.
- Los títulos de sección del template están en inglés como guía de estructura, pero tu CONTENIDO debe estar completamente en el idioma del usuario.
