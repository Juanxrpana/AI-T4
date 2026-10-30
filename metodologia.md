# 1. PLANIFICACIÓN DE LA AUDITORÍA INFORMÁTICA

## 1.1 Identificación del proyecto

| Dato | Detalle |
|---|---|
| Sistema | Sistema de gestión para el Centro de Especialidades Médicas Jehová Rafa (SISTEMA CEM JEHOVÁ RAFA) |
| Participantes | Dixon Bastias, Juan Silva, Wilmer Báez y Edouard Sandoval |
| Tutora asesora | Carmen Colmenares |
| Institución | Universidad Politécnica Territorial Andrés Eloy Blanco, El Tocuyo, estado Lara |
| Tipo de intervención | Auditoría informática con pruebas de sistema, integración, portabilidad, rendimiento, seguridad y servidor |
| Inicio de ejecución | Semana 5 del cronograma de actividades |
| Duración estimada | Ocho semanas (semana 5 a semana 12) |

Las semanas son relativas al encargo: la semana 5 corresponde a la primera semana de ejecución de la auditoría, no a una fecha calendario oficial.

## 1.2 Criterio de priorización por riesgo

Probar de forma exhaustiva un sistema de este tamaño es inviable: no se pueden ejercitar todas las combinaciones de entradas y condiciones, por lo que el esfuerzo se dirige según el riesgo y la normativa aplicable (ISO/IEC/IEEE 29119-2, 2021; ISO 19011, 2018). En el CEM Jehová Rafa el riesgo no se distribuye por igual entre módulos: un fallo en Pacientes, Citas o Control Médico afecta la atención del paciente; un fallo en Facturación afecta el cobro; y un fallo en Usuarios o Roles expone información clínica. Por eso se auditan los 19 módulos, pero se aplican pruebas profundas de caja negra a los de mayor riesgo.

| Módulo / componente | Por qué es crítico | Prueba profunda aplicada |
|---|---|---|
| Pacientes | Concentra los datos personales y es la base de toda la operación | Caja negra, integración y datos de frontera |
| Citas | Un error produce solapamiento de horarios y pacientes sin atención | Caja negra y datos de fecha/hora |
| Control médico | Guarda la información clínica del paciente | Caja negra, integración y longitud de texto |
| Facturación | Un error genera cobros incorrectos o pérdidas | Caja negra y datos monetarios |
| Doctores (directorio médico) | De él depende la derivación correcta del paciente | Caja negra e integración |
| Usuarios, Roles y Bitácora | Controlan el acceso a la información sensible | Caja negra y pruebas de seguridad |
| Insumos | El stock y los vencimientos condicionan la atención | Caja negra y datos de cantidad |
| Resto de módulos (10) | Menor impacto operativo | Navegación y verificación funcional |

## 1.3 Objetivos

**General:** validar que el sistema cumple los requisitos funcionales y no funcionales del SRS, detectar errores antes de la implementación en producción y asegurar su calidad, seguridad y usabilidad.

**Específicos:**

1. Verificar la lógica del backend PHP con pruebas unitarias automatizadas.
2. Comprobar el comportamiento de los módulos desde la perspectiva del usuario (navegación y caja negra).
3. Validar la integración entre interfaz, backend y base de datos.
4. Comprobar que la interfaz web y la API devuelven resultados equivalentes (prueba en paralelo).
5. Evaluar la portabilidad en navegadores y resoluciones representativas, así como el funcionamiento en diferentes sistemas operativos (local vs. servidor VPS).
6. Medir el comportamiento ante picos de carga (spike) y ante ciclos repetitivos prolongados (huracán).
7. Inspeccionar la configuración del servidor y verificar la resistencia a inyección SQL.
8. Evaluar el funcionamiento de la aplicación móvil en Android (iOS queda fuera de alcance).
9. Registrar defectos, proponer acciones correctivas y planificar el retesteo.

## 1.4 Alcance

| Elemento auditado | Qué se audita | Pruebas aplicadas |
|---|---|---|
| Backend PHP | Reglas de negocio, validaciones y cálculos | Unitarias |
| 19 módulos del sistema | Navegación y operación desde la perspectiva del usuario | Funcionales de caja negra |
| Interfaz, backend y base de datos | Flujo y sincronización de la información entre las tres capas | Integración |
| Interfaz web y API | Equivalencia de resultados por ambas vías | En paralelo |
| Navegadores y resoluciones | Consistencia visual y funcional en Chrome y Firefox, 4 resoluciones, local y VPS | Portabilidad |
| Endpoints web y móviles | Comportamiento ante ráfagas y ciclos prolongados | Picos (spike) y huracán |
| Aplicación móvil Android | Autenticación, navegación, sesión, conectividad y endpoints | Funcionales y de integración |
| Servidor VPS | Configuración, servicios expuestos, permisos y respaldos | Inspección de solo lectura |
| Formularios y filtros | Resistencia a inyección SQL (16 casos y 59 payloads no destructivos) | Seguridad |
| Usuarios representativos | Aceptación y usabilidad | Sesiones con usuarios |

**Módulos (19):** Inicio de sesión, Pacientes, Clientes, Citas, Control médico, Hospitalización, Insumos, Entrada, Facturación, Proveedores, Doctores, Servicios, Patologías, Usuarios, Roles, Bitácora, Reportes, Estadísticas y Perfil.

**Fuera de alcance:** escaneos activos o destructivos, pruebas de estrés hasta el punto de fallo, servicios de terceros, validación en iOS y el componente inteligente MIDI (se aborda al final, cuando la tutora entregue la información correspondiente).

## 1.5 Criterios de entrada y salida

**Criterios de entrada.** No se inicia la ejecución hasta que cada condición esté verificada:

| Condición de entrada | Responsable de verificarla | Evidencia |
|---|---|---|
| Ambiente disponible y autorizado | Todos | Acta de inicio |
| Cuentas de prueba por rol (administrador, secretaría, doctor) | Wilmer Báez | Listado de cuentas |
| Datos sintéticos identificables | Juan Silva | Lote de datos con prefijo `AUDIT-` |
| Versiones registradas del sistema y del ambiente | Edouard Sandoval | Tabla de versiones (Apache, PHP, MariaDB) |
| Copia de seguridad de la base de datos y forma de detener la carga | Edouard Sandoval | Respaldo lógico |
| Casos, resultados esperados y responsables acordados | Dixon Bastias | Planillas aprobadas |

**Criterios de salida:**

1. Cada caso con evidencia y estado (Planificado, Pasó, Falló, Bloqueado o No ejecutado).
2. Defectos con pasos de reproducción, impacto y prioridad.
3. Incidencias críticas de seguridad cerradas solo con corrección y retesteo.
4. Análisis final que separe lo realizado de lo pendiente.

## 1.6 Riesgos y limitaciones

| Riesgo | Probabilidad | Impacto | Tratamiento |
|---|---|---|---|
| Pruebas en ambiente local | Alta | Medio | Repetir carga y seguridad en preproducción |
| Carga desde una sola IP y sesión | Alta | Medio | Separar respuestas 2xx de las 429 y rotular el límite de 60 peticiones por 10 s |
| Sin participantes en las sesiones | Alta | Medio | Programar sesiones de aceptación y usabilidad (iOS queda fuera de alcance) |
| Restauración de respaldos no ejecutada | Media | Alto | Simulacro autorizado de recuperación |
| Métricas locales no comparables con el VPS | Alta | Bajo | Rotular cada resultado con su ambiente |
| Datos reales expuestos durante las pruebas | Media | Alto | Usar solo datos sintéticos y borrarlos al cierre |

## 1.7 Módulos y orden de ejecución

El orden es secuencial porque cada etapa consume los insumos de la anterior: no se puede probar carga sin un ambiente estable, ni analizar defectos sin resultados registrados.

1. Respaldo del ambiente.
2. Pruebas unitarias.
3. Pruebas funcionales (caja negra).
4. Pruebas de integración.
5. Pruebas de la aplicación móvil.
6. Pruebas de portabilidad.
7. Pruebas de picos.
8. Pruebas de huracán.
9. Pruebas en paralelo.
10. Inspección del servidor.
11. Inyección SQL.
12. Análisis de defectos y retesteo.

## 1.8 Ambientes de prueba

| Ambiente | Rol | Configuración | Uso en la auditoría |
|---|---|---|---|
| Windows + XAMPP | Estación local | Apache 2.4.58, PHP 8.2.12, MariaDB (XAMPP) | Desarrollo, aplicación móvil y pruebas de carga web |
| Linux Mint 22.3 | Equipo de un desarrollador | XAMPP, Apache 2.4.58, PHP 8.2.12, MariaDB 10.4.32 | Pruebas del servidor y ejecución funcional completa |
| VPS (producción) | Despliegue real | Apache 2.4.69, PHP 8.4, MariaDB 10.11.10; 1 vCPU AMD EPYC, 961 MB RAM | Revisión básica, portabilidad de sistema operativo e inspección de solo lectura |

Las métricas de carga obtenidas en el ambiente local no son comparables con las del VPS debido a la diferencia de recursos de hardware (1 núcleo y 961 MB de RAM en el VPS). Cada resultado se rotula con el ambiente correspondiente.

## 1.9 Equipo y responsabilidades

| Integrante | Responsabilidad | Evidencia que entrega |
|---|---|---|
| Edouard Sandoval | Pruebas de picos, huracán, portabilidad y unitarias | Reporte PHPUnit, tablas de carga y matriz de portabilidad |
| Dixon Bastias | Pruebas funcionales y de carga (PF-02) | Planillas PF-02, métricas de carga |
| Juan Silva | Pruebas funcionales e integración (PF-01, PF-03, PF-04, INT-01 a INT-07) | Planillas PF e INT con capturas y logs |
| Wilmer Báez | Pruebas funcionales, carga y seguridad SQL (PF-05, P01 a P04, SQL-01 a SQL-16) | Planillas PF-05, matrices P y SQL |
| Carmen Colmenares | Tutora asesora: acompañamiento metodológico | Observaciones y visto bueno |

## 1.10 Cronograma de actividades

El encargo se ejecuta en ocho pasos secuenciales, uno por semana, desde la semana 5. Cada paso deja un entregable que alimenta al siguiente.

| Semana | Paso | Actividades | Módulos / componentes | Responsable | Evidencia |
|---|---|---|---|---|---|
| **5** | 1. Planeación y preparación | Definir alcance y criterios; levantar el inventario de los 19 módulos; respaldar la base de datos; crear cuentas por rol; registrar versiones de Apache, PHP y MariaDB; verificar conexión y equipos; dejar constancia de la autorización del ambiente | Transversal | Todos | Acta de inicio, inventario de módulos, respaldo lógico |
| **6** | 2. Diseño de casos y datos | Elaborar las planillas de caja negra por módulo; definir los lotes de datos válidos, inválidos y de frontera; preparar los 16 casos y 59 payloads de inyección SQL; definir el guion de carga (spike en 3 fases y huracán); armar la matriz requisito → caso | Pacientes, Citas, Facturación, Doctores | Juan Silva, Dixon Bastias | Planillas, matriz de datos, guion de pruebas |
| **7** | 3. Unitarias e integración | Ejecutar PHPUnit sobre el backend; correr INT-01 a INT-07 (interfaz, PHP y MariaDB); registrar el resultado de cada caso | Backend PHP y base de datos | Edouard Sandoval, Juan Silva | Reporte PHPUnit, planillas INT con evidencia |
| **8** | 4. Caja negra: módulos clínicos y administrativos | Navegar los 19 módulos; aplicar caja negra profunda en Pacientes, Citas, Control médico, Doctores, Usuarios y Roles; validar campos obligatorios, formatos y mensajes de error | 19 módulos | Dixon Bastias, Wilmer Báez | Planillas PF-01 y PF-03, listado de defectos |
| **9** | 5. Caja negra: módulos financieros y aplicación móvil | Probar Facturación, Servicios, Insumos, Proveedores, Reportes y Estadísticas; en Android validar autenticación, navegación, sesión, conectividad y endpoints | Facturación, Insumos, App Android | Dixon Bastias, Wilmer Báez | Planillas PF-02 y PF-05, reporte móvil |
| **10** | 6. Portabilidad y rendimiento | Probar Chrome y Firefox en 4 resoluciones, local y VPS; ejecutar spike (3 fases) y huracán; separar respuestas 2xx de las 429; rotular cada métrica con su ambiente | Web, API y móvil | Edouard Sandoval | Matriz de portabilidad, tablas de tiempos y errores |
| **11** | 7. Seguridad y servidor | Inspeccionar el VPS en modo de solo lectura (servicios expuestos, versiones, permisos y respaldos); ejecutar SQL-01 a SQL-16 con los 59 payloads; ejecutar P01 a P04 | Login, búsquedas, filtros y VPS | Wilmer Báez | Informe de servidor, matrices SQL y P |
| **12** | 8. Análisis, retesteo y cierre | Comparar respuesta esperada con la obtenida; clasificar los hallazgos; retestear los casos corregidos; emitir el veredicto por módulo y el informe final con limitaciones y recomendaciones | Todos | Todos | Informe final de auditoría |

## 1.11 Definición de las pruebas a usar

Cada prueba se eligió por el riesgo que cubre en este sistema, no por catálogo genérico.

| Prueba | Por qué se usa en el CEM Jehová Rafa | Dónde se aplica | Herramienta | Datos que emplea |
|---|---|---|---|---|
| **Unitarias (caja blanca)** | Verificar de forma aislada las reglas de negocio antes de tocar la interfaz: cálculo de montos, validación de cédula, control de stock y manejo de claves | Backend PHP: modelos y validaciones | PHPUnit | Numéricos, cadenas, nulos y valores de frontera |
| **Funcionales (caja negra)** | Comprobar que la secretaría y el médico completan el flujo real: registrar paciente, agendar cita, emitir factura y abrir un control médico | 19 módulos; profundas en Pacientes, Citas, Facturación, Directorio médico y Control médico | Planillas manuales y capturas | Válidos, inválidos, vacíos y de frontera |
| **Integración** | El sistema tiene tres capas: un contrato roto entre interfaz, PHP y MariaDB detiene el flujo aunque cada pieza funcione por separado | INT-01 a INT-07: interfaz, backend y base de datos | Peticiones HTTP, PDO y logs | Registros creados y consultados en las tres capas |
| **En paralelo (web frente a API)** | Confirmar que la API devuelve lo mismo que la interfaz, para que un mismo dato no se vea distinto según la vía de acceso | Mismo caso por interfaz y por API | Peticiones paralelas | El mismo juego de datos por ambas vías |
| **Portabilidad** | La clínica no trabaja con un solo equipo ni un solo navegador: se verifica que el layout y la operación no se rompan al cambiar de entorno | Chrome y Firefox en 4 resoluciones, local y VPS | Navegadores y capturas | Datos funcionales repetidos por entorno |
| **Picos (spike)** | En horas pico la secretaría agenda en ráfaga; se mide si el sistema colapsa o responde con lentitud | Endpoints web y móviles, en 3 fases | BOT de envío sincronizado | Ráfagas de peticiones concurrentes |
| **Huracán** | Resistencia sostenida: detecta degradación progresiva, fugas de sesión y crecimiento de recursos | Endpoints y sesiones | BOT en ciclo prolongado | Peticiones repetitivas hasta el límite del sistema |
| **Inyección SQL** | La base guarda historia clínica; una inyección filtraría o alteraría datos sensibles | Login, búsquedas y filtros | 16 casos y 59 payloads no destructivos | Cadenas maliciosas controladas |
| **Servidor** | La configuración del VPS puede exponer la aplicación aunque el código esté correcto: versiones, servicios, permisos y respaldos | VPS, en modo de solo lectura | Comandos de inspección | Configuración y servicios |
| **Aplicación móvil** | Es un canal alterno de acceso: se valida que sesión, conectividad y endpoints se comporten igual que en web | Android | Dispositivo o emulador | Credenciales y datos de prueba |
| **Aceptación y usabilidad** | El sistema lo usa personal no técnico; un error de usabilidad produce registros erróneos | Sesiones con usuarios representativos | Guion de tareas | Casos reales de secretaría |

## 1.12 Tipos de datos de las pruebas

**A. Tipos de datos y valores de entrada**

| Tipo de dato | Campo ejemplo en el sistema | Válido | Inválido | Frontera o límite | Qué se valida |
|---|---|---|---|---|---|
| Numérico entero | Cédula, teléfono | `12345678` | `V-1234A`, letras | 1 y 10 dígitos, ceros a la izquierda | Rechazo de no numéricos y longitud |
| Alfanumérico | Nombre, apellido | `María Pérez` | Vacío, solo espacios | 1 y 60 caracteres | Obligatoriedad y longitud |
| Texto libre | Motivo de consulta, observaciones | `dolor abdominal` | `<script>`, emojis | Cadena muy larga | Codificación y desbordamiento |
| Fecha | Fecha de cita, control, vencimiento de insumo | `2026-10-30` | `31/02/2026`, `0000-00-00` | Hoy, ayer, más de 6 meses | Rango y formato |
| Hora o bloque | Horario de cita | `08:30` | `25:00` | Hora de apertura y de cierre | Solapamiento de citas |
| Monetario | Monto de factura, precio de servicio | `150,00` | `-50`, texto | `0,00` y monto máximo | Cálculo y redondeo |
| Cantidad o stock | Insumos | `25` | `-3` | `0` | Descuento y stock negativo |
| Booleano o estado | Activo, pagado, atendida | `1` | `2`, `null` | — | Consistencia de estados |
| Credenciales | Usuario, clave, correo | `usuario@cem.com` | Correo sin `@` | Longitud mínima y máxima | Autenticación y formato |
| Catálogo o selección | Especialidad, rol | Valor existente en el catálogo | Valor inexistente | — | Que solo acepte valores del catálogo |
| JSON y cabeceras | Cuerpo de la API, `X-API-Key` | JSON bien formado | JSON truncado, clave errónea | Payload mínimo y máximo | Contrato del endpoint |
| Malicioso | Login, búsqueda | — | `' OR '1'='1`, `UNION SELECT` | 59 payloads | Resistencia a inyección |

**B. Lotes de prueba**

| Lote | Contenido | Uso |
|---|---|---|
| Datos sintéticos | Registros con prefijo `AUDIT-` (paciente, doctor, cita, factura) | Identificar y borrar lo creado sin usar datos reales |
| Datos válidos | Un juego completo por módulo | Camino feliz |
| Datos inválidos | Tipo incorrecto, vacío o fuera de catálogo | Mensajes de error y rechazo |
| Datos de frontera | Cero, negativos, longitud máxima, fecha límite | Robustez |
| Datos de carga | Ráfagas y ciclos repetitivos | Rendimiento |
| Datos maliciosos | Payloads SQL no destructivos | Seguridad |

**C. Cruce con la planilla (ejemplo del módulo Pacientes)**

| Campo | Tipo | Escenario | Valor de entrada | Respuesta esperada |
|---|---|---|---|---|
| Cédula | Numérico | Correcto | `12345678` | Guarda y muestra el paciente |
| Cédula | Numérico | Incorrecto | `12AB` | Mensaje «cédula inválida», no guarda |
| Cédula | Numérico | Frontera | Vacío | Mensaje de campo obligatorio |
| Nombre | Alfanumérico | Frontera | 60 caracteres | Guarda completo, sin truncar |
| Correo | Credencial | Incorrecto | `paciente.cem.com` | Rechaza por falta de `@` |
| Fecha de cita | Fecha | Incorrecto | `31/02/2026` | Rechaza fecha inexistente |
| Motivo de consulta | Texto libre | Incorrecto | `<script>alert(1)</script>` | Guarda como texto, no ejecuta |

## 1.13 Componente inteligente MIDI

Componente pendiente de definición: la tutora entregará la información correspondiente. Cuando se reciba, se incorporará como fase final del encargo con su propio paso en el cronograma, sin alterar las semanas 5 a 12. Las pruebas previstas son:

| Prueba | Por qué se usaría | Dónde |
|---|---|---|
| Integración PHP y FastAPI | El componente consulta datos por HTTP; una cabecera o clave mal gestionada rompe la orientación | Endpoints `/orientar` y `/Api` |
| Contrato de respuesta | La interfaz espera un JSON definido; un campo faltante deja el chat sin respuesta | Esquema de respuesta |
| No determinismo | El modelo puede variar entre ejecuciones; el mismo caso debe repetirse para comparar | Repetición del mismo caso |
| Catálogo real | El componente no puede sugerir especialidades inexistentes | Validación contra catálogo |
| Privacidad | La respuesta no debe volcar datos de pacientes | Respuestas generadas |
| Carga del endpoint | La latencia del modelo condiciona la experiencia de la secretaría | Ráfagas sobre `/orientar` |
