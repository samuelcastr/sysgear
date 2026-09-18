# PLAN DE EJECUCIÓN — gearctl

> Estado actual estimado: **~10–15%** de un producto distribuible.
> Lo que existe: esqueleto modular (detección, catálogo, selección de backend,
> GUI shell, instalador básico). Lo que falta: **control real de hardware**,
> macros, efectos RGB, perfiles, persistencia, calidad y distribución.

---

## FASE 1 — Control real de hardware (núcleo del producto)
**Objetivo:** que mover un ajuste en la GUI cambie algo físico en el dispositivo.
**Sin esto, todo lo demás es decoración.**

- [x] 1.1 DPI / sensibilidad: leer y fijar DPI por niveles (vía `RatbagDriver` D-Bus contra `ratbagd`; verificado en Logitech G203 046d:c092).
- [x] 1.2 Polling rate: lectura/escritura (verificado 1000→500→1000Hz en G203).
- [ ] 1.3 Reasignación de botones: mapear botones del mouse a teclas/acciones.
- [x] 1.4 Prueba física obligatoria: cada ajuste se valida contra hardware real (no mocks).
- [ ] 1.5 Tabla de verdad por modelo: qué ajuste funciona en qué VID:PID (matriz de capacidades reales, no declaradas).

**Criterio de salida:** cambiar DPI desde la GUI y verificarlo en el SO/juego.

## FASE 2 — Macros (grabación y reproducción)
- [ ] 2.1 Grabador global de eventos (teclado + mouse) multiplataforma.
- [ ] 2.2 Editor de macros: ver/editar/retardos entre pulsaciones.
- [ ] 2.3 Reproducción con temporización fiel + tecla de parada de emergencia.
- [ ] 2.4 Asignación macro → tecla programable del dispositivo (vía SDK donde exista).
- [ ] 2.5 Límites anti-abuso: retardos mínimos, advertencia en juegos competitivos.

**Criterio de salida:** grabar "Ctrl+C, Ctrl+V con 200 ms" y reproducirlo en cualquier app.

## FASE 3 — RGB avanzado (efectos, no solo color fijo)
- [ ] 3.1 Motor de efectos propio: estático, respiración, ola, reactivo, espectro.
- [ ] 3.2 RGB por zona/tecla (donde el hardware lo permita).
- [ ] 3.3 Sincronización OpenRGB completa (modos, brillo, velocidad).
- [ ] 3.4 Preview en la GUI antes de aplicar al hardware.
- [ ] 3.5 Efectos de bajo consumo / apagado por inactividad.

**Criterio de salida:** 3 efectos corriendo en hardware real + preview fiel.

## FASE 4 — Perfiles
- [ ] 4.1 Guardar/cargar perfil completo (DPI + macros + RGB) por dispositivo.
- [ ] 4.2 Auto-switch: cambiar de perfil según la aplicación en foco.
- [ ] 4.3 Import/export de perfiles (compartir archivos `.gearctl.json`).
- [ ] 4.4 Perfiles de fábrica / reset seguro.

**Criterio de salida:** abrir un juego → perfil "FPS" se activa solo.

## FASE 5 — Persistencia y configuración
- [ ] 5.1 Config en `~/.config/gearctl/` (Linux) / `%APPDATA%` (Windows), formato JSON versionado.
- [ ] 5.2 Migraciones de esquema entre versiones.
- [ ] 5.3 Logs rotativos + modo debug (`--debug`).

## FASE 6 — Experiencia de escritorio
- [ ] 6.1 Bandeja del sistema (tray) con cambio rápido de perfil.
- [ ] 6.2 Autostart + inicio minimizado.
- [ ] 6.3 Atajos globales (ej. cambiar DPI con hotkey).
- [ ] 6.4 Notificaciones de conexión/desconexión de dispositivos.
- [ ] 6.5 Idiomas ES/EN (i18n con Qt Linguist).

## FASE 7 — Calidad (puerta de entrada a distribución)
- [ ] 7.1 Suite `pytest`: detección, BD, selección de backend, degradados.
- [ ] 7.2 CI (GitHub Actions): lint + tests en Linux y Windows.
- [ ] 7.3 Cobertura mínima 70% en `db/`, `drivers/`, `security/`.
- [ ] 7.4 `ruff`/`mypy` en pre-commit.

## FASE 8 — Distribución Windows
- [ ] 8.1 PyInstaller afinado: icono, metadata, `--noconsole`, exclusión de peso muerto.
- [ ] 8.2 Instalador Inno Setup (`.iss`): asistente, desinstalador, accesos directos.
- [ ] 8.3 Firma de código (certificado) — requisito para SmartScreen.
- [ ] 8.4 Auto-update (canal estable/beta).

## FASE 9 — Distribución Linux
- [ ] 9.1 Reglas udev empaquetadas (permisos sin root).
- [ ] 9.2 `.desktop` + icono + autostart.
- [ ] 9.3 AppImage o Flatpak.

## FASE 10 — Seguridad y firmware (endurecimiento)
- [ ] 10.1 Huellas SHA-256 reales en `TRUSTED_PUBLISHERS` + verificación de firma.
- [ ] 10.2 Catálogo remoto firmado (firma Ed25519, no solo hash).
- [ ] 10.3 Política de ejecución: allowlist de binarios, sin rutas relativas.
- [ ] 10.4 Auditoría: log de cada acción sobre hardware.

## FASE 11 — Nube opcional (solo si la visión la incluye)
- [ ] 11.1 Backend mínimo: cuentas + sync de perfiles + catálogo remoto.
- [ ] 11.2 Modo offline-first (la nube nunca bloquea el uso local).

## FASE 12 — Documentación y comunidad (si será open-source)
- [ ] 12.1 Guía de usuario con capturas, FAQ, troubleshooting.
- [ ] 12.2 Guía de contribución + templates de issues/PR.
- [ ] 12.3 Licencia definida (GPL-3.0/MIT) antes del primer release público.

---

## Hitos y versiones

| Versión | Contenido | Valor para el usuario |
|---------|-----------|----------------------|
| **v0.2** | Fase 1 completa | "Por fin controla mi mouse de verdad" |
| **v0.5** | Fases 2 + 3 | Macros y RGB con efectos |
| **v0.8** | Fases 4 + 5 + 6 | Perfiles automáticos, app usable a diario |
| **v1.0** | Fases 7 + 8 + 9 | Instalable en ambos SO, con tests |
| **v1.x** | Fases 10 + 11 + 12 | Endurecido, nube, comunidad |

**Regla de oro:** no se avanza de fase sin cumplir su *criterio de salida*
contra **hardware real**. Los mocks sirven para tests, no para dar fases por hechas.

## Orden de ejecución recomendado

```
F1 (hardware) → F5 (persistencia) → F2 (macros) → F3 (RGB) → F4 (perfiles)
     → F6 (UX) → F7 (calidad) → F8/F9 (distribución) → F10/F11/F12
```

F5 va segunda porque macros, efectos y perfiles **necesitan dónde guardarse**;
hacerlos antes obligaría a reescribirlos.
