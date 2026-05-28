# AIntelligence - Local Agent Bot

## Descripción del Proyecto
Este componente corresponde al agente de automatización local de AIntelligence, desarrollado para ejecutarse de manera nativa en entornos de escritorio basados en el sistema operativo Windows. Su función principal consiste en automatizar flujos de navegación dentro de plataformas profesionales utilizando emulaciones de comportamiento humano, extraer información estructurada y sincronizar dichos datos de forma automatizada tanto con el panel web central como con los servicios de almacenamiento externos.

## Componentes Críticos de Ejecución
El script de automatización utiliza controladores de navegador asistidos para interactuar con interfaces dinámicas de usuario. Al ejecutarse localmente, consume los recursos del navegador del sistema operativo del trabajador. Además, el bot se integra con Celery para la gestión asíncrona de las tareas.

## Configuración Inicial y Archivos Requeridos
Por razones de seguridad estricta, el repositorio no incluye claves de acceso ni configuraciones de identidad. Antes de proceder con la ejecución o compilación del programa, se deben situar los siguientes archivos en el directorio raíz del código fuente:

* `.env`: Archivo de texto que define las variables de entorno locales, incluyendo las URL de la API de la nube y los tokens de validación temporal.
* `credentials.json`: Archivo de autenticación en formato JSON provisto por la consola de desarrolladores de Google Cloud. Habilita los permisos necesarios para interactuar con las API de almacenamiento.
* `token.json`: Este archivo se genera de manera automática la primera vez que el script se ejecuta de forma local tras solicitar el consentimiento OAuth2 al usuario. Una vez concedido, almacena las credenciales de actualización de forma segura.

## Proceso de Compilación de Ejecutables
Para distribuir el bot a los usuarios finales de la empresa sin requerir que estos tengan instalado Python, el entorno de desarrollo debe compilar el script en un único archivo ejecutable independiente (.exe). El proceso se realiza mediante PyInstaller.

Debido a la complejidad de las dependencias asíncronas (Celery/Kombu) y la inyección de controladores web, PyInstaller requiere instrucciones explícitas para no omitir módulos durante el análisis estático.

Pasos para realizar la compilación:
1. Abrir la terminal de comandos en la raíz del proyecto.
2. Asegurarse de tener activo el entorno virtual de Python correspondiente.
3. Ejecutar el siguiente comando de compilación exacto:

```bash
pyinstaller --onefile --name "AIntelligence_Bot" --collect-all celery --collect-all kombu --hidden-import="celery.concurrency.threads" --hidden-import="services" --hidden-import="services.tasks" --hidden-import="services.linkedin_bot" --hidden-import="chromedriver_autoinstaller" run_bot.py

```
## Desglose Técnico de los Parámetros Utilizados

* `--onefile`: Compacta todo el código fuente y librerías en un único archivo ejecutable.
* `--name`: Asigna el nombre final del archivo generado.
* `--collect-all`: Fuerza la inclusión de todos los subpaquetes y datos de librerías complejas que PyInstaller suele omitir.
* `--hidden-import`: Obliga al compilador a incluir módulos internos e importaciones dinámicas que no son detectables mediante el árbol de dependencias estándar.
* `run_bot.py`: Archivo principal de ejecución del agente.

## Protocolo de Despliegue y Distribución

Una vez concluido de manera exitosa el proceso de compilación, PyInstaller creará una carpeta llamada `dist` dentro del directorio de trabajo. El archivo resultante dentro de esa carpeta debe distribuirse al servidor en la nube para actualizar el paquete de descarga de los usuarios:

1. Localizar el archivo generado `AIntelligence_Bot.exe` dentro del directorio `dist/`.
2. Acceder al administrador de archivos del servidor web (Plesk) donde opera la aplicación central.
3. Navegar hasta el directorio del proyecto web: `AIntelligence_Cloud_App/bot_releases/`.
4. Subir y reemplazar el ejecutable antiguo por esta nueva versión estable.
5. Asegurarse de que el archivo `credentials.json` corporativo coexista en la misma carpeta del servidor para garantizar que las descargas de los usuarios incluyan toda la paquetería lista para el uso inmediato.
