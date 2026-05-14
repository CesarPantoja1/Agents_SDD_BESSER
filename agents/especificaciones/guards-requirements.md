# Guards para Requirements

## Reglas de trazabilidad (derivar del Discovery)
- SOLO genera requisitos para features EXPLÍCITAMENTE listadas en Scope In del Discovery.
- Si no estás seguro si una feature está en Scope In, NO la incluyas.
- NUNCA generes requisitos para features que estén en Scope Out.
- Cada requisito DEBE referenciar el item de Scope In del que deriva (puedes añadir una nota breve).
- NO dupliques obligaciones: un mismo comportamiento no debe estar en dos requisitos distintos.

## Reglas de formato EARS (Acceptance Criteria)
- Cada requisito DEBE tener al menos un acceptance criterion en formato EARS.
- EARS keywords (When, If, While, Where, The system shall) DEBEN estar en inglés.
- El contenido variable (eventos, condiciones, acciones) DEBE estar en el idioma del usuario.
- Ejemplo correcto en español: `When el usuario hace clic en reservar, el sistema shall validar la disponibilidad`.
- Ejemplo correcto en inglés: `When user clicks checkout, the system shall validate cart contents`.

## Reglas de contenido
- Requirements es WHAT, not HOW.
- PROHIBIDO mencionar frameworks (React, Laravel, Vue, Next.js, Django, etc.).
- PROHIBIDO mencionar librerías (Prisma, Redux, Axios, etc.).
- PROHIBIDO mencionar bases de datos (PostgreSQL, MongoDB, MySQL, etc.).
- PROHIBIDO mencionar patrones de arquitectura (MVC, Hexagonal, Clean Architecture, etc.).
- Los requisitos describen comportamiento observable por el usuario u operador.
- Si detectas que un requisito suena a "cómo implementar", reescríbelo como "qué debe hacer el sistema".

## Reglas de estructura
- Usa IDs numéricos secuenciales: Requirement 1, Requirement 2, etc.
- NO uses IDs alfabéticos (Requirement A, B, C).
- Cada requisito debe tener: Objective (como X, quiero Y, para Z) + Acceptance Criteria (EARS).
- Agrupa requisitos relacionados en áreas lógicas pero mantén IDs globales secuenciales.

## Regla de idioma
- Detecta el idioma del mensaje del usuario y genera TODO el artefacto en ese mismo idioma.
- Los keywords EARS (When, If, While, Where, The system shall) se mantienen en inglés.
- Los títulos de sección del template están en inglés como guía de estructura, pero tu CONTENIDO debe estar completamente en el idioma del usuario.
