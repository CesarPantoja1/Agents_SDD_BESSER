# Guards para Diagrama de Clases

## Reglas de Generación
1. Cada clase DEBE tener al menos 3 atributos relevantes al dominio.
2. Las relaciones DEBEN incluir multiplicidades explícitas (1, 0..1, 0..*, 1..*).
3. NO generar getters/setters como métodos.
4. Usar PascalCase para nombres de clases y camelCase para atributos/métodos.
5. Las enumeraciones DEBEN usar isEnumeration=true y listar valores como atributos sin tipo.
6. El diagrama debe reflejar fielmente las entidades descritas en Requirements y Design.
7. NO inventar clases que no tengan soporte en las fases anteriores.
8. Incluir relaciones de herencia solo cuando esté justificado por el diseño.
9. NO incluir coordenadas de posición en la salida del LLM (el layout engine las calcula).
10. Generar el diagrama en el mismo idioma que las especificaciones del usuario.
