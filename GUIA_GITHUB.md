# Guía: paper trading automático + panel en el celular

Resultado final: GitHub ejecuta el bot solo cada día a las 7:30 pm (Ecuador), te avisa por Telegram
y actualiza un panel web que instalas en tu celular. Todo gratis. Sigue SIMULADO (sin dinero real).

## A. Subir el proyecto a GitHub
1. Crea una cuenta gratis en github.com (si no tienes).
2. Arriba a la derecha toca "+" -> "New repository". Nombre: `paper-trading`. Elige **Public**.
   No marques "Add a README". Toca "Create repository".
   (Público porque la versión gratuita de GitHub solo publica el panel desde repositorios públicos.
   Solo contiene datos SIMULADOS. Nunca subas claves de ningún exchange.)
3. Descomprime `trading_bot_github.zip` en tu computadora.
4. En tu repositorio nuevo toca "uploading an existing file". Arrastra TODO el contenido de la
   carpeta descomprimida, incluidas las carpetas `.github` y `docs`. Toca "Commit changes".
   - Si después no ves la carpeta `.github`: "Add file" -> "Create new file", escribe como nombre
     `.github/workflows/diario.yml` y pega el contenido de ese archivo.

## B. Traer tu paper trading actual (MUY IMPORTANTE)
5. En Google Drive, carpeta `trading_bot`, descarga `paper_state.json`, `paper_trades.csv`
   y `paper_equity.csv`.
6. Súbelos a la **raíz** del repositorio ("Add file" -> "Upload files").
   Sin `paper_state.json` el workflow se niega a correr, para no borrar tu historial.
7. **Desde este momento deja de ejecutar el bot en Colab.** Si lo corres en los dos lados, tendrás
   dos historiales distintos. Conserva la copia de Drive como respaldo.

## C. Activar el panel web
8. En el repositorio: Settings -> Pages -> "Build and deployment" -> Source: **GitHub Actions**.

## D. Avisos por Telegram (opcional, recomendado)
9. En Telegram busca @BotFather, escribe `/newbot`, elige nombre y usuario. Te dará un **token**.
10. Escríbele cualquier mensaje a tu bot nuevo. Luego abre en el navegador:
    `https://api.telegram.org/botTU_TOKEN/getUpdates` y busca `"chat":{"id":` seguido de un número.
    Ese número es tu **chat id**.
11. En GitHub: Settings -> Secrets and variables -> Actions -> "New repository secret".
    Crea `TELEGRAM_TOKEN` (el token) y `TELEGRAM_CHAT_ID` (el número).
    **No pegues el token en ningún chat ni archivo.**

## E. Primera ejecución
12. Pestaña **Actions** -> "Paper trading v3 (diario)" -> "Run workflow" (deja `nuevo` sin marcar).
    Espera 1-2 minutos hasta ver la marca verde.
13. Tu panel queda en: `https://TU_USUARIO.github.io/paper-trading/`
14. En el celular ábrelo en Chrome -> menú ⋮ -> "Instalar app" / "Agregar a pantalla de inicio".

## Problemas comunes
- **Rojo en Actions:** abre la ejecución y copia el mensaje de error. Si ves "Falta paper_state.json", repite el paso 6.
- **El panel dice "No pude cargar los datos":** ejecuta el workflow una vez a mano (paso 12).
- **GitHub avisa que desactivó el workflow:** pasa en repos sin actividad por mucho tiempo.
  Entra a Actions y toca "Enable workflow".
- **El aviso de hoy llegó tarde:** GitHub puede retrasar los horarios programados. No afecta el resultado,
  porque el bot usa velas ya cerradas.
