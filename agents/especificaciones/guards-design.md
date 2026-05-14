# Guards para Design

## Reglas anti-placeholder y anti-template-regurgitation (CRÍTICAS)
- **PROHIBIDO** copiar texto instruccional del template como contenido final. Ejemplos de lo que NO debe aparecer: `2-3 párrafos máximo`, `[valor específico]`, `[usuarios objetivo]`, `[nombre y breve justificación]`, `[cómo se separan las responsabilidades]`, `[lista de patrones clave]`, etc.
- **PROHIBIDO** dejar placeholders sin rellenar como `[...]`, `{{...}}`, o listas genéricas del template.
- **PROHIBIDO** incluir el bloque meta del template (`Propósito`, `Enfoque`, `Advertencia`, `Warning`, `Purpose`, `Approach`) en el output final. Esas son instrucciones para el autor del template, no contenido del documento.
- Si una sección NO aplica al proyecto, **OMÍTELA COMPLETAMENTE**. No la dejes con texto genérico, placeholders o instrucciones del template.
- Si una sección SÍ aplica, **DEBE contener contenido específico del proyecto** derivado del Discovery y Requirements. Cero texto genérico.
- El documento final debe parecerse a una especificación real, no a un template parcialmente rellenado.

## Reglas de trazabilidad (derivar de Requirements)
- Extrae TODOS los IDs numéricos de requisitos del contexto de Requirements proporcionado.
- CADA requisito con ID DEBE aparecer en la sección "Requirements Traceability" del diseño.
- CADA componente del diseño DEBE listar los req IDs que satisface (formato: `Requirements: 1, 2.1, 3`).
- NO generes componentes que no respondan a un requisito existente.
- Si un requisito no tiene un componente claro que lo satisfaga, reconsidera el diseño o divide el requisito.

## Reglas de stack técnico
- El stack técnico DEBE ser EXACTAMENTE el definido en la sección Approach del Discovery.
- NO cambies tecnologías sin una justificación explícita y visible.
- Si el Approach dice Laravel + PostgreSQL, usa Laravel + PostgreSQL.
- Si el Approach dice React + Node.js, usa React + Node.js.
- La sección Technology Stack del Design debe reflejar fielmente el Approach del Discovery.

## Reglas de contenido
- Design es HOW, not WHAT. No repitas los requisitos; mapea a ellos por ID.
- Define interfaces, contratos y boundaries. NO escribas código de implementación.
- Mantén el documento conciso: si supera 1000 líneas, simplifica o divide en specs separadas.
- Respeta la dirección de dependencias definida en el Discovery / Estructura.
- Usa diagramas Mermaid SOLO cuando clarifiquen interacciones no obvias.

## Reglas de estructura
- La sección Boundary Commitments DEBE definir qué posee este spec y qué no.
- La sección Requirements Traceability DEBE ser una tabla: Requirement ID | Summary | Component(s).
- Cada componente detallado DEBE tener: Intent, Requirements (IDs), Dependencies, Contracts.

## Regla de idioma
- Detecta el idioma del mensaje del usuario y genera TODO el artefacto en ese mismo idioma.
- Los títulos de sección del template están en inglés como guía de estructura, pero tu CONTENIDO debe estar completamente en el idioma del usuario.
