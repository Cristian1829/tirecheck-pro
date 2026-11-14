# Chatbot de WhatsApp para clientes

Los clientes le escriben a un número de WhatsApp de la empresa y pueden:
- preguntar en lenguaje libre, por ejemplo *"¿qué carros de este mes tienen llantas para cambio inmediato?"*;
- pedir el informe de inspección en PDF de una placa;
- pedir el informe consolidado de flota en PDF.

El bot solo muestra los clientes y sedes que el usuario tiene asignados en TireCheck, igual que la página web.

## Cómo funciona
1. **Vinculación.** El cliente escribe al número. Si su celular no está vinculado, recibe un enlace de un solo uso que vence en 10 minutos.
2. **Inicio de sesión.** En esa página entra con su usuario y contraseña de TireCheck. La contraseña nunca se escribe en el chat. Desde ese momento el celular queda unido a su usuario.
3. **Respuestas.** Cada pregunta la interpreta Google Gemini, que llama a las consultas de `whatsapp/herramientas.py`. Gemini nunca accede a la base directamente.
4. **Desvinculación.** El cliente escribe *salir*. El vínculo también cae solo si al usuario le cambian la clave, cierran sus sesiones o lo desactivan.

| Archivo | Qué hace |
|---|---|
| `whatsapp/rutas.py` | Webhook, vinculación y página `/whatsapp/vincular` |
| `whatsapp/proveedor_meta.py` | Conexión con WhatsApp Cloud API: firma, envío de texto y PDF |
| `whatsapp/agente.py` | Gemini con *function calling* |
| `whatsapp/herramientas.py` | Consultas permitidas: cambio inmediato, próximas a cambio, resumen, última inspección y PDF |
| `whatsapp/almacen.py` | Tablas `whatsapp_*` en la misma base SQLite |
| `templates/vincular_whatsapp.html` | Página de inicio de sesión para vincular |

## Variables de entorno (en Railway, nunca en el repositorio)
| Variable | De dónde sale |
|---|---|
| `WHATSAPP_TOKEN` | Token permanente del usuario del sistema (Meta Business → Usuarios del sistema) |
| `WHATSAPP_PHONE_ID` | App de Meta → WhatsApp → Configuración de la API → *Phone number ID* |
| `WHATSAPP_APP_SECRET` | App de Meta → Configuración → Básica → *Clave secreta de la app* |
| `WHATSAPP_VERIFY_TOKEN` | Un texto que usted inventa; se escribe igual en Meta al registrar el webhook |
| `GEMINI_API_KEY` | Google AI Studio → *Get API key*. Use un proyecto con facturación: en el nivel gratuito Google puede usar los datos. |
| `GEMINI_MODELO` | Opcional. Si no se pone o ya no existe, el bot elige solo el Gemini Flash-Lite más nuevo disponible (se ve en el log: `Modelo de Gemini en uso`) |
| `URL_PUBLICA` | Opcional. Por ejemplo `https://midominio.com`. Si no se pone, se usa el dominio público de Railway. |
| `WHATSAPP_ROLES` | Opcional. Roles que pueden usar el bot. Por defecto `gerencia,gerente,jefatura,jefe,jefe_llantas`. Los inspectores y el administrador no se vinculan. |
| `WHATSAPP_API_VERSION` | Opcional. Por defecto `v25.0` |

## Paso a paso de configuración en Meta
1. **Portafolio comercial.** Créelo en business.facebook.com con el nombre legal de la empresa.
2. **Verificación del negocio.** Vaya a Configuración → Centro de seguridad y suba el RUT o la Cámara de Comercio. Tarda de unos días a 2 semanas. Mientras tanto se puede probar con el número de prueba.
3. **App de Meta.** En developers.facebook.com cree una app de tipo *Empresa* y agréguele el producto **WhatsApp**. Meta crea un número de prueba gratis.
4. **Token permanente.** En Configuración del negocio → Usuarios del sistema:
   - cree un usuario con rol de administrador;
   - asígnele la app y la cuenta de WhatsApp;
   - genere un token con los permisos `whatsapp_business_messaging` y `whatsapp_business_management`.
5. **Webhook.** En la app, vaya a WhatsApp → Configuración → Webhook:
   - URL de devolución: `https://<dominio-railway>/api/whatsapp/webhook`;
   - token de verificación: el mismo valor de `WHATSAPP_VERIFY_TOKEN`;
   - suscriba el campo **messages**.
6. **Número real.** Cuando la empresa esté verificada:
   - agregue la línea nueva, que no puede tener WhatsApp instalado, y verifíquela por SMS o llamada;
   - configure el nombre visible y el logo;
   - cambie `WHATSAPP_PHONE_ID` por el del número real.
7. **Método de pago.** Agréguelo en el Administrador de WhatsApp.

## Prueba local
```bash
python server.py
```
```bash
cloudflared tunnel --url http://localhost:8000
```
- Use la URL que da el túnel como webhook en Meta y como `URL_PUBLICA`.
- Desde un celular agregado como destinatario de prueba en la app de Meta:
  1. escriba *hola*;
  2. vincule el celular con un usuario de rol gerencia o jefatura;
  3. pregunte por los vehículos con cambio inmediato.

## Costos aproximados
Verifique las tarifas vigentes de Meta y Google antes de activar.
- **Meta:** los primeros 1.000 mensajes de servicio al mes por número son gratis; luego cuestan ~US$0,0008 cada uno en Colombia. Las respuestas a lo que el cliente pregunta son mensajes de servicio.
- **Gemini Flash-Lite:** cuesta ~US$0,002 por pregunta.
- **Servidor:** sin costo adicional, porque se usa el mismo Railway.
