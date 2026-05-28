import os
import time
import random
import logging
import subprocess 
import winreg
from typing import Any
import undetected_chromedriver as uc
import chromedriver_autoinstaller
from selenium.webdriver.common.by import By

from config import BROWSER_PROFILE_DIR
from database import update_lead_status, log_activity
from task_manager import update_task, get_task
from logging_config import setup_logging

logger = setup_logging()

worker_drivers: dict[int, Any] = {}

def kill_zombie_chrome():
    """🛡️ Fuerza bruta: Mata cualquier proceso de Chrome huérfano en Windows"""
    try:
        subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe', '/T'], capture_output=True)
        logger.info("⚔️ Procesos huérfanos de Chrome eliminados del sistema.")
    except Exception:
        pass

def safe_sleep(seconds, task_id=None, user_id=None, driver=None):
    """
    Lee la base de datos para ver si Flask ha cambiado el estado a 'paused' o 'stopped'.
    🛡️ Además, verifica el latido (heartbeat) del navegador cada segundo si se pasa el driver.
    """
    if not task_id:
        time.sleep(seconds)
        return

    for _ in range(int(seconds)):
        # 1. Verificar si el usuario ha cerrado el navegador manualmente
        if driver:
            try:
                # Comprobación ultrarrápida para ver si la ventana sigue existiendo
                _ = driver.window_handles 
            except Exception:
                raise RuntimeError("🛑 Navegador cerrado manualmente por el usuario. Abortando tarea.")

        # 2. Verificar base de datos de tareas
        task = get_task(task_id)
        if not task:
            return
            
        status = str(task.get("status", "")).lower()
        
        if status in ["stopped", "canceled"]:
            raise InterruptedError("Proceso detenido por el usuario.")
            
        while status == "paused":
            update_task(task_id, message="⏸ Paused...")
            time.sleep(2)
            task = get_task(task_id)
            status = str(task.get("status", "")).lower() if task else "stopped"
            if status in ["stopped", "canceled"]:
                raise InterruptedError("Proceso detenido por el usuario.")
                
        time.sleep(1)

def get_driver(user_id: int):
    global worker_drivers
    if user_id in worker_drivers:
        driver = worker_drivers[user_id]
        try:
            if not driver.window_handles:
                raise Exception("Navegador sin ventanas abiertas.")
            _ = driver.current_url 
            return driver
        except Exception as e:
            logger.warning(f"🧟‍♂️ Navegador zombi detectado. Limpiando memoria... ({e})")
            try: driver.quit()
            except: pass
            del worker_drivers[user_id]
            kill_zombie_chrome()

    user_profile_dir = os.path.join(BROWSER_PROFILE_DIR, f"user_{user_id}")
    os.makedirs(user_profile_dir, exist_ok=True)
    
    for lf in ["SingletonLock", "SingletonCookie", "LOCK"]:
        lf_path = os.path.join(user_profile_dir, lf)
        if os.path.exists(lf_path):
            try: os.remove(lf_path)
            except: pass

    def create_opts():
        opts = uc.ChromeOptions()
        
        # 🛡️ FIX CRÍTICO: Parche para la nueva versión de Selenium
        opts.headless = False 
        
        opts.add_argument(f"--user-data-dir={user_profile_dir}")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-popup-blocking")
        
        if os.getenv("HEADLESS", "false").lower() == "true":
            opts.headless = True  # Mantenemos el parche también aquí
            opts.add_argument("--headless=new")
            
        return opts

    # 🔍 DETECTOR SENIOR DE CHROME LOCAL
    try:
        clave = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon")
        version_completa, _ = winreg.QueryValueEx(clave, "version")
        version_local = int(version_completa.split('.')[0])
    except Exception:
        try:
            # Fallback por si se instaló a nivel de sistema completo
            clave = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe")
            version_local = 148 # Valor seguro si todo lo demás falla
        except Exception:
            version_local = None

    # 🚀 INICIALIZACIÓN BLINDADA ANTI-VERSIONES
    try:
        if version_local:
            logger.info(f"🌐 Forzando Driver compatible con Chrome versión: {version_local}")
            driver = uc.Chrome(options=create_opts(), use_subprocess=True, keep_alive=True, version_main=version_local)
        else:
            chromedriver_autoinstaller.install() 
            driver = uc.Chrome(options=create_opts(), use_subprocess=True, keep_alive=True)
    except Exception as e:
        logger.warning(f"Chrome subprocess error: {e}")
        if version_local:
            driver = uc.Chrome(options=create_opts(), keep_alive=True, version_main=version_local)
        else:
            driver = uc.Chrome(options=create_opts(), keep_alive=True)

    worker_drivers[user_id] = driver
    return driver

JS_SHADOW_HELPERS = """
function _shadowQuery(sel, root) {
    root = root || document;
    if (root.querySelector) {
        var el = root.querySelector(sel);
        if (el) return el;
    }
    var hosts = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
    for (var h of hosts) {
        if (h.shadowRoot) {
            var found = _shadowQuery(sel, h.shadowRoot);
            if (found) return found;
        }
    }
    return null;
}
function _shadowQueryAll(sel, root) {
    root = root || document;
    var results = root.querySelectorAll ? Array.from(root.querySelectorAll(sel)) : [];
    var hosts = root.querySelectorAll ? Array.from(root.querySelectorAll('*')) : [];
    for (var h of hosts) {
        if (h.shadowRoot) {
            results = results.concat(_shadowQueryAll(sel, h.shadowRoot));
        }
    }
    return results;
}
"""

def get_profile_action_status(driver) -> str:
    return driver.execute_script("""
        var root = document.querySelector('.pv-top-card') || document.querySelector('main') || document;
        var candidates = Array.from(root.querySelectorAll("button, a, [role='button']"));
        var statusMap = {
            message : ['mensaje', 'message', 'enviar mensaje', 'send message'],
            connect : ['conectar', 'connect'],
            pending : ['pendiente', 'pending', 'invitation sent', 'solicitud enviada'],
            follow  : ['seguir', 'follow'],
        };
        for (var el of candidates) {
            var txt   = (el.innerText  || el.textContent || '').trim().toLowerCase();
            var label = (el.getAttribute('aria-label') || '').toLowerCase();
            for (var [status, keywords] of Object.entries(statusMap)) {
                for (var kw of keywords) {
                    if (txt === kw || label === kw || label.startsWith(kw + ' ')) return status;
                }
            }
        }
        return 'unknown';
    """)
    
def _click_action_button(driver, keywords_es: list, keywords_en: list) -> bool:
    all_kw = [k.lower() for k in keywords_es + keywords_en]
    return bool(driver.execute_script("""
        var kws = arguments[0];
        var root = document.querySelector('.pv-top-card') || document.querySelector('main') || document;
        var els = Array.from(root.querySelectorAll("button, a, [role='button']"));
        for (var el of els) {
            var txt   = (el.innerText || el.textContent || '').trim().toLowerCase();
            var label = (el.getAttribute('aria-label') || '').toLowerCase();
            for (var kw of kws) {
                if (txt === kw || label === kw || label.startsWith(kw + ' ')) { el.click(); return true; }
            }
        }
        return false;
    """, all_kw))

def click_connect_button(driver) -> bool:
    return _click_action_button(driver, ["conectar"], ["connect"])

def click_message_button(driver) -> bool:
    return _click_action_button(driver, ["mensaje", "enviar mensaje"], ["message", "send message"])

def click_more_menu(driver) -> bool:
    return _click_action_button(driver, ["más"], ["more"])

def click_connect_in_dropdown(driver) -> bool:
    return driver.execute_script("""
        var items = Array.from(document.querySelectorAll(
            "div.artdeco-dropdown__content li, div[class*='dropdown'] li, [role='menuitem']"
        ));
        for (var el of items) {
            var txt = (el.innerText || el.textContent || '').trim().toLowerCase();
            if (txt === 'conectar' || txt === 'connect') { el.click(); return true; }
        }
        return false;
    """)

def enviar_invitacion_con_nota(driver, mensaje_seguro: str, user_id: int, task_id: str = None) -> bool:
    safe_sleep(2, task_id=task_id, driver=driver)
    tiene_nota = bool(mensaje_seguro and mensaje_seguro.strip())
    if tiene_nota:
        clicked_note = driver.execute_script(JS_SHADOW_HELPERS + """
            var btn = _shadowQuery('[aria-label*="note"], [aria-label*="nota"]');
            if (!btn) {
                var allBtns = _shadowQueryAll('button');
                btn = allBtns.find(b => {
                    var t = (b.innerText || '').toLowerCase();
                    return t.includes('add a note') || t.includes('añadir nota');
                });
            }
            if (btn) { btn.click(); return true; }
            return false;
        """)
        if clicked_note:
            safe_sleep(1.5, task_id=task_id, driver=driver)
            typed = driver.execute_script(JS_SHADOW_HELPERS + """
                var ta = _shadowQuery('textarea[name="message"], textarea#custom-message, textarea');
                if (ta && ta.offsetParent !== null) {
                    ta.focus();
                    ta.value = arguments[0];
                    ta.dispatchEvent(new Event('input',  {bubbles: true}));
                    ta.dispatchEvent(new Event('change', {bubbles: true}));
                    return true;
                }
                return false;
            """, mensaje_seguro)
            if not typed:
                try:
                    for ta in driver.find_elements(By.CSS_SELECTOR, "textarea"):
                        if ta.is_displayed():
                            ta.clear()
                            ta.send_keys(mensaje_seguro)
                            break
                except Exception: pass
            safe_sleep(1.5, task_id=task_id, driver=driver)
            
    enviado = driver.execute_script(JS_SHADOW_HELPERS + """
        var activeModal = document.querySelector('[role="dialog"]') || document;
        var allBtns = _shadowQueryAll('button', activeModal);
        var sendBtn = allBtns.find(b => {
            if (b.disabled) return false;
            var cls   = (b.className || '').toLowerCase();
            var txt   = (b.innerText || '').trim().toLowerCase();
            if (txt.includes('enviar sin nota') || txt.includes('send without')) return true;
            if (txt.includes('enviar') || txt.includes('send')) return true;
            if (cls.includes('artdeco-button--primary')) return true;
            return false;
        });
        if (sendBtn) { sendBtn.click(); return true; }
        return false;
    """)
    return bool(enviado)
    
def _cerrar_chat_overlay_shadow(driver):
    try:
        driver.execute_script(JS_SHADOW_HELPERS + """
            var closeBtn = _shadowQuery('button[aria-label*="close" i], button[aria-label*="cerrar" i], button[aria-label*="dismiss" i]');
            if (closeBtn) closeBtn.click();
        """)
    except Exception: pass

def enviar_mensaje_directo(driver, mensaje_seguro: str, user_id: int, task_id: str = None, max_retries: int = 2) -> bool:
    for attempt in range(1, max_retries + 1):
        box = driver.execute_script(JS_SHADOW_HELPERS + """
            return _shadowQuery('.msg-form__contenteditable[role="textbox"]');
        """)
        if not box:
            click_message_button(driver)
            safe_sleep(3, task_id=task_id, driver=driver)
            continue
        try:
            driver.execute_script("""
                var el = arguments[0];
                var texto = arguments[1];
                el.scrollIntoView({block:'center'});
                el.focus();
                el.innerHTML = ''; 
                document.execCommand('insertText', false, texto);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            """, box, mensaje_seguro)
        except Exception:
            try:
                box.clear()
                box.send_keys(mensaje_seguro)
            except: pass
            
        safe_sleep(2, task_id=task_id, driver=driver)
        send_btn = driver.execute_script(JS_SHADOW_HELPERS + """
            var btns = _shadowQueryAll('button');
            return btns.find(b => {
                if (b.disabled) return false;
                var txt = (b.innerText || '').toLowerCase();
                var cls = (b.className || '').toLowerCase();
                return cls.includes('msg-form__send-button') || txt === 'enviar' || txt === 'send';
            });
        """)
        if send_btn:
            try:
                driver.execute_script("arguments[0].click();", send_btn)
                safe_sleep(2, task_id=task_id, driver=driver)
                _cerrar_chat_overlay_shadow(driver)
                return True
            except Exception: pass
        else:
            try:
                send_btn_2 = driver.execute_script(JS_SHADOW_HELPERS + """
                    var btns = _shadowQueryAll('button');
                    return btns.find(b => !b.disabled && (b.className.includes('msg-form__send-button') || b.innerText.toLowerCase() === 'enviar'));
                """)
                if send_btn_2:
                    driver.execute_script("arguments[0].click();", send_btn_2)
                    safe_sleep(2, task_id=task_id, driver=driver)
                    _cerrar_chat_overlay_shadow(driver)
                    return True
            except Exception: pass
    return False

def esperar_inicio_sesion(driver, url_destino: str, task_id: str = None):
    """Detecta si estamos en la pantalla de login y pausa el bot hasta que el usuario entre."""
    bloqueos = ["login", "signup", "checkpoint", "authwall"]
    
    try:
        current_url = driver.current_url.lower()
    except Exception:
        raise RuntimeError("🛑 Navegador cerrado manualmente por el usuario. Abortando tarea.")
        
    esta_bloqueado = any(b in current_url for b in bloqueos)
    
    if esta_bloqueado:
        logger.info("🔒 LinkedIn pide inicio de sesión. El bot te espera (tómate tu tiempo)...")
        
        while True:
            try:
                current_url = driver.current_url.lower()
            except Exception:
                raise RuntimeError("🛑 Navegador cerrado manualmente por el usuario. Abortando tarea.")
                
            if not any(b in current_url for b in bloqueos):
                break
            safe_sleep(3, task_id=task_id, driver=driver)
            
        logger.info("✅ Sesión iniciada detectada. Redirigiendo al perfil correcto...")
        try:
            driver.get(url_destino)
        except Exception:
            raise RuntimeError("🛑 Navegador cerrado manualmente por el usuario. Abortando tarea.")
            
        safe_sleep(5, task_id=task_id, driver=driver)

def process_profile(driver, url: str, name: str, mensaje_base: str, user_id: int, company: str = "", job_title: str = "", task_id: str = None) -> dict:
    try:
        driver.get(url)
    except Exception:
        raise RuntimeError("🛑 Navegador cerrado manualmente por el usuario. Abortando tarea.")
        
    safe_sleep(3, task_id=task_id, driver=driver)
    
    # 🛑 ACTIVAMOS EL CENTINELA DE SESIÓN
    esperar_inicio_sesion(driver, url_destino=url, task_id=task_id)
    
    safe_sleep(random.uniform(2, 4), task_id=task_id, driver=driver)
    
    first_name = name.split()[0] if name else "there"
    mensaje_final = mensaje_base.replace("{name}", first_name)
    if company: mensaje_final = mensaje_final.replace("{company}", company)
    if job_title: mensaje_final = mensaje_final.replace("{job_title}", job_title)
    mensaje_final = mensaje_final.strip()

    status = get_profile_action_status(driver)
    logger.info(f"👤 Candidato procesado — LinkedIn: [{status}]")
    result = {"action": status, "success": False, "status_found": status}

    if status == "pending":
        logger.info("⏳ El candidato ya tiene una solicitud pendiente.")
        return result
        
    if status == "message":
        logger.info("💬 Enviando mensaje directo de conexión...")
        click_message_button(driver)
        safe_sleep(2, task_id=task_id, driver=driver)
        exito = False
        try: exito = enviar_mensaje_directo(driver, mensaje_final, user_id, task_id=task_id) 
        except Exception as e: logger.warning(f"⚠️ Error mensaje directo: {e}")
        finally:
            result["success"] = exito
            if exito: update_lead_status(url, "messaged", user_id)
            log_activity("messages", url, exito, user_id)
            
    elif status in ["connect", "follow", "unknown"]:
        clicked = click_connect_button(driver)
        if not clicked:
            click_more_menu(driver)
            safe_sleep(1, task_id=task_id, driver=driver)
            clicked = click_connect_in_dropdown(driver)
            
        if clicked:
            safe_sleep(1.5, task_id=task_id, driver=driver)
            exito = False
            try: exito = enviar_invitacion_con_nota(driver, mensaje_final, user_id, task_id=task_id) 
            except Exception as e: logger.warning(f"⚠️ Error invitación: {e}")
            finally:
                result["success"] = exito
                if exito: update_lead_status(url, "invited", user_id)
                log_activity("connections", url, exito, user_id)
                
    try:
        driver.execute_script("var c = document.querySelector('button[aria-label=\"Dismiss\"], button[aria-label=\"Cerrar\"]'); if(c) c.click();")
    except: pass
    
    return result