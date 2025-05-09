# 1. Assurez-vous d'avoir installé les packages via pip :
# pip install selenium pillow requests google-generativeai tenacity webdriver-manager

import requests
import time
import os
import io
from PIL import Image
import shutil
from selenium import webdriver
from selenium.webdriver.chrome.service import Service # MODIFIÉ
from webdriver_manager.chrome import ChromeDriverManager # MODIFIÉ
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException as SeleniumTimeoutException
import glob
import google.generativeai as genai
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import re

# --- CRUCIAL: Clear potential proxy settings ---
# Ceci devrait fonctionner de la même manière sous Windows
proxy_vars_to_clear = ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy', 'ALL_PROXY', 'all_proxy']
for var_name in proxy_vars_to_clear:
    if var_name in os.environ:
        print(f"Clearing environment variable: {var_name}")
        del os.environ[var_name]
os.environ['NO_PROXY'] = '*'
# --- END CRUCIAL SECTION ---

# Configuration
actifs = ["EURUSD"]
CONTEXT_ASSETS = ["TVC:DXY"]
timeframes_init = ["60", "240", "1D", "1W"]
timeframes_monitor = ["1", "5", "15"]

# --- API KEY MANAGEMENT ---
gemini_api_key = "VOTRE_CLE_API_GEMINI_ICI" # REMPLACEZ PAR VOTRE VRAIE CLÉ

if not gemini_api_key or "VOTRE_CLE_API_GEMINI_ICI" in gemini_api_key or "AIzaSyB" not in gemini_api_key: # Modifié pour mieux correspondre à la chaîne par défaut
    raise ValueError("GEMINI_API_KEY n'est pas définie ou est toujours la valeur par défaut. Veuillez définir votre clé API réelle.")
# --- END API KEY MANAGEMENT ---

# MODIFIÉ: Utilisation de chemins relatifs pour Windows (ou chemins absolus si vous préférez)
# Ces dossiers seront créés dans le répertoire où le script est exécuté.
chemin_base = os.getcwd() # Répertoire courant du script
chemin_enregistrement = os.path.join(chemin_base, "screenshots")
chemin_pdf = os.path.join(chemin_base, "pdf_files") # Dossier pour les PDF

os.makedirs(chemin_enregistrement, exist_ok=True)
os.makedirs(chemin_pdf, exist_ok=True)

# Configure Gemini
try:
    genai.configure(api_key=gemini_api_key)
except Exception as e:
    print(f"Error configuring Gemini: {e}")
    raise

def reset_environnement():
    for folder in [chemin_enregistrement]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
        os.makedirs(folder)
    print("Screenshot environment reset")

def prendre_screenshot_tradingview(actif, timeframe):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    # options.add_argument("--no-sandbox") # Moins pertinent/nécessaire sous Windows standard
    # options.add_argument("--disable-dev-shm-usage") # Spécifique à Linux
    options.add_argument("--window-size=1920,1200")
    # options.binary_location = "/usr/bin/chromium-browser" # SUPPRIMÉ - Non applicable à Windows

    driver = None
    try:
        print(f"Initializing Chrome WebDriver for {actif} {timeframe}...")
        # MODIFIÉ: Utilisation de ChromeDriverManager pour gérer le chromedriver.exe
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
    except WebDriverException as e:
        print(f"WebDriverException during Chrome initialization for {actif} {timeframe}: {e}")
        print("Ensure Google Chrome is installed and webdriver-manager can download chromedriver.exe.")
        return None
    except Exception as e:
        print(f"Generic error initializing Chrome browser for {actif} {timeframe}: {e}")
        return None

    tv_timeframe = timeframe
    if timeframe == "1D": tv_timeframe = "D"
    elif timeframe == "1W": tv_timeframe = "W"

    url_actif = actif.replace(":", "%3A")
    url = f"https://www.tradingview.com/chart/?symbol={url_actif}&interval={tv_timeframe}"
    print(f"Navigating to: {url}")
    try:
        driver.get(url)
    except Exception as e:
        print(f"Error navigating to URL {url}: {e}")
        if driver: driver.quit()
        return None

    # Le nom de fichier utilise os.path.join, ce qui est correct pour Windows
    nom_fichier = os.path.join(chemin_enregistrement, f"{actif.replace(':', '_')}_{timeframe}_{int(time.time())}.png")

    try:
        WebDriverWait(driver, 45).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.chart-markup-table, div.tv-chart"))
        )
        print(f"Chart container found for {actif} {timeframe}. Waiting for elements to settle...")
        time.sleep(15)

        popups_selectors = [
            "button[aria-label='Close']", "button[aria-label='Fermer']",
            "div[class*='popup'] button[class*='close']", "button#onetrust-accept-btn-handler",
            "button.tv-dialog__close", "button[data-name='accept-all-cookies']"
        ]
        for selector in popups_selectors:
            try:
                close_buttons = driver.find_elements(By.CSS_SELECTOR, selector)
                for close_button in close_buttons:
                    if close_button.is_displayed() and close_button.is_enabled():
                        print(f"Attempting to close popup with selector: {selector} for {actif}")
                        driver.execute_script("arguments[0].click();", close_button)
                        time.sleep(2)
                        print(f"Clicked popup with selector: {selector} for {actif}")
                        break
            except Exception:
                pass

        print(f"Attempting to save screenshot for {actif} {timeframe} to {nom_fichier}")
        driver.save_screenshot(nom_fichier)
        print(f"Screenshot {actif} {timeframe} saved to {nom_fichier}")
        return nom_fichier
    except SeleniumTimeoutException:
        print(f"Timeout waiting for chart elements for {actif} {timeframe}.")
        debug_html_path = os.path.join(chemin_enregistrement, f"{actif.replace(':', '_')}_{timeframe}_debug_timeout.html")
        try:
            with open(debug_html_path, "w", encoding="utf-8") as f: f.write(driver.page_source)
            print(f"Saved page source to {debug_html_path}")
        except Exception as e_html: print(f"Could not save page source: {e_html}")
        return None
    except Exception as e:
        print(f"Error capturing screenshot for {actif} {timeframe}: {e}")
        debug_html_path = os.path.join(chemin_enregistrement, f"{actif.replace(':', '_')}_{timeframe}_debug_error.html")
        try:
            with open(debug_html_path, "w", encoding="utf-8") as f: f.write(driver.page_source)
            print(f"Saved page source to {debug_html_path}")
        except Exception as e_html: print(f"Could not save page source: {e_html}")
        return None
    finally:
        if driver:
            driver.quit()

def trouver_pdfs():
    if not os.path.exists(chemin_pdf):
        print(f"PDF directory not found: {chemin_pdf}")
        return None
    # glob.glob fonctionne bien sous Windows avec les séparateurs os.sep
    pdfs = glob.glob(os.path.join(chemin_pdf, "*.pdf"))
    if pdfs:
        print(f"Found PDF: {pdfs[0]}")
        return pdfs[0]
    else:
        print(f"No PDF found in {chemin_pdf}")
        return None

def initialiser_session_gemini():
    model = genai.GenerativeModel('gemini-1.5-flash-latest')
    chat = model.start_chat(history=[])
    return chat

RETRYABLE_GEMINI_EXCEPTIONS = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    TimeoutError
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type(RETRYABLE_GEMINI_EXCEPTIONS),
    reraise=True
)
def send_message_to_gemini_with_retry(chat_session, content_parts, operation_description="Gemini API call"):
    print(f"Attempting to send message for: {operation_description}")
    response = chat_session.send_message(content_parts, request_options={'timeout': 180.0})
    print(f"Successfully sent message for: {operation_description}")
    return response

def envoyer_analyse_initiale(chat, chemins_images_dict, pdf_path=None, primary_asset_symbol=None, context_asset_symbols=None):
    if context_asset_symbols is None: context_asset_symbols = []
    print(f"Sending initial analysis. PDF path: {pdf_path}")
    intro_actifs = f"l'actif principal {primary_asset_symbol}"
    if context_asset_symbols:
        intro_actifs += f" et l'actif de contexte {', '.join(context_asset_symbols)}"

    content_parts = [
        "ANALYSE INITIALE - Vous êtes un expert en analyse technique ICT (Inner Circle Trader) et votre mission est de fournir une analyse approfondie et exploitable.",
        f"Vous allez recevoir des graphiques multi-timeframes (HTF) pour {intro_actifs}: " + ", ".join(timeframes_init) + " et potentiellement un document PDF de référence.",
        "Votre objectif est de préparer le terrain pour identifier une opportunité de trading à haute probabilité sur l'ACTIF PRINCIPAL.",
        "\n**Principes ICT Clés à intégrer IMPÉRATIVEMENT dans votre analyse :**",
        "1.  **Structure du Marché (Market Structure) :** Pour chaque actif (principal et contexte), identifiez les derniers BOS et MSS.",
        "2.  **Points d'Intérêt (POI) :** Pour chaque actif, décrivez les FVG, OB, Breaker/Mitigation Blocks.",
        "3.  **Liquidité :** Identifiez les pools BSL/SSL et IDM pour chaque actif.",
        "4.  **Premium/Discount Arrays :** Évaluez pour chaque actif.",
        "5.  **Confluence des Signaux :** Mettez en évidence.",
        "6.  **ANALYSE DU DXY (si fourni et pertinent) et CORRÉLATION :**",
        "    *   Analysez la structure, les POI, et la liquidité du DXY.",
        "    *   Quel est le biais directionnel probable du DXY ?",
        "    *   **CRUCIAL :** Comment la situation actuelle et les perspectives du DXY influencent-elles l'actif principal ? (Ex: DXY haussier suggère EURUSD baissier, et vice-versa).",
        "    *   Recherchez activement les **SMT (Smart Money Technique) Divergences** entre le DXY et l'actif principal sur les HTF. Signalez toute divergence claire.",
        "\n**Instructions pour l'analyse du PDF (si fourni) :**",
        "Si un document PDF est joint, analysez son contenu et intégrez ses informations clés dans votre évaluation des graphiques et du DXY.",
    ]
    for asset_type, image_paths in chemins_images_dict.items():
        asset_name_display = primary_asset_symbol if asset_type == "primary" else (context_asset_symbols[0] if context_asset_symbols else "context_asset")
        content_parts.append(f"\n--- GRAPHIQUES POUR {asset_name_display.upper()} ({asset_type.upper()}) ---")
        for img_path in image_paths:
            try:
                print(f"Opening image for {asset_name_display}: {img_path}")
                img = Image.open(img_path)
                tf_from_filename = "HTF"
                try:
                    parts = os.path.basename(img_path).split('_')
                    idx = 2 if asset_name_display.count('_') > 0 or ':' in asset_name_display else 1
                    tf_from_filename = parts[idx]
                except IndexError: pass
                content_parts.append(f"\nGraphique {os.path.basename(img_path)} ({asset_name_display}, Timeframe approx. {tf_from_filename}):")
                content_parts.append(img)
            except FileNotFoundError: print(f"ERROR: Image file not found: {img_path}")
            except Exception as e: print(f"Erreur chargement image {img_path}: {e}")

    if pdf_path:
        try:
            print(f"Uploading PDF: {pdf_path}")
            if os.path.exists(pdf_path):
                uploaded_file = genai.upload_file(path=pdf_path)
                content_parts.append("\nDocument de référence (PDF) fourni. Veuillez l'analyser et l'intégrer:")
                content_parts.append(uploaded_file)
                print(f"PDF {pdf_path} uploaded successfully.")
            else: print(f"ERROR: PDF file not found at path: {pdf_path}")
        except Exception as e: print(f"Erreur chargement ou upload PDF {pdf_path}: {e}")

    content_parts.append(f"""
    \n**Format de Réponse Demandé pour l'Analyse Initiale (Focus sur {primary_asset_symbol}):**
    1.  **Analyse du DXY ({', '.join(context_asset_symbols) if context_asset_symbols else 'N/A'}) :** ...
    2.  **Synthèse Globale & Biais Directionnel HTF pour {primary_asset_symbol} (Tenant compte du DXY) :** ...
    3.  **Inventaire Détaillé des POI HTF Clés pour {primary_asset_symbol} :** ...
    4.  **Scénarios ICT Prospectifs pour {primary_asset_symbol} (Haussier et Baissier) :** ...
    5.  **Plan de Monitoring pour {primary_asset_symbol} ({", ".join(timeframes_monitor)}) :** ...
    """) # Prompts détaillés omis pour la concision, ils restent les mêmes
    print("Sending initial prompt to Gemini...")
    try:
        response = send_message_to_gemini_with_retry(chat, content_parts, f"Analyse Initiale {primary_asset_symbol} & DXY")
        print("=== ANALYSE INITIALE COMPLETE DE GEMINI ===")
        print(response.text)
        print("==========================================")
        return True
    except Exception as e:
        print(f"Error sending initial analysis to Gemini: {e}")
        return False

def parse_float_from_text(text_value):
    if text_value is None: return None
    try:
        cleaned_text = re.split(r'\s|[(]', str(text_value))[0]
        return float(cleaned_text.replace(',', '.'))
    except ValueError:
        print(f"Warning: Could not parse float from '{text_value}'")
        return None

def extract_trade_parameters(text):
    entry, sl, tp, direction = None, None, None, None
    if "TRADE CONFIRME: LONG" in text.upper(): direction = "LONG"
    elif "TRADE CONFIRME: SHORT" in text.upper(): direction = "SHORT"
    entry_match = re.search(r"(?:NIVEAU D'ENTRÉE PRÉCIS|ENTRÉE)\s*:\s*([0-9.,]+(?:\s*\(.*\))?)", text, re.IGNORECASE)
    sl_match = re.search(r"(?:NIVEAU DE STOP LOSS \(SL\)|SL)\s*:\s*([0-9.,]+(?:\s*\(.*\))?)", text, re.IGNORECASE)
    tp_match = re.search(r"(?:NIVEAU DE TAKE PROFIT \(TP\)|TP)\s*:\s*([0-9.,]+(?:\s*\(.*\))?)", text, re.IGNORECASE)
    if entry_match: entry = parse_float_from_text(entry_match.group(1))
    if sl_match: sl = parse_float_from_text(sl_match.group(1))
    if tp_match: tp = parse_float_from_text(tp_match.group(1))
    if direction and entry is not None and sl is not None and tp is not None:
        return {"direction": direction, "entry": entry, "sl": sl, "tp": tp, "status": "OPEN"}
    return None

def extract_trade_management_updates(text, current_trade):
    updates = {"action": "MAINTENIR"}
    if re.search(r"CLÔTURER LE TRADE", text, re.IGNORECASE):
        updates["action"] = "CLOTURER"
        reason_match = re.search(r"(?:RAISON|JUSTIFICATION)\s*:\s*(.+)", text, re.IGNORECASE)
        updates["reason"] = reason_match.group(1).strip() if reason_match else "Suggestion de Gemini"
        return updates
    sl_update_match = re.search(r"(?:NOUVEAU SL|AJUSTER SL(?: À)?)\s*:\s*([0-9.,]+(?:\s*\(.*\))?)", text, re.IGNORECASE)
    tp_update_match = re.search(r"(?:NOUVEAU TP|AJUSTER TP(?: À)?)\s*:\s*([0-9.,]+(?:\s*\(.*\))?)", text, re.IGNORECASE)
    sl_val = parse_float_from_text(sl_update_match.group(1)) if sl_update_match else None
    tp_val = parse_float_from_text(tp_update_match.group(1)) if tp_update_match else None
    if sl_val is not None and sl_val != current_trade.get("sl"):
        updates["new_sl"] = sl_val
        updates["action"] = "AJUSTER"
    if tp_val is not None and tp_val != current_trade.get("tp"):
        updates["new_tp"] = tp_val
        updates["action"] = "AJUSTER"
    if updates["action"] == "AJUSTER":
        justification_match = re.search(r"JUSTIFICATION\s*:\s*(.+)", text, re.IGNORECASE)
        updates["justification"] = justification_match.group(1).strip() if justification_match else "Ajustement suggéré"
    return updates

def analyser_screenshot_monitoring(chat, chemin_image_primaire, chemin_image_dxy, timeframe_actuel, actif_primaire_symbol, dxy_symbol, active_trade_details=None):
    print(f"Analyzing {timeframe_actuel}m for {actif_primaire_symbol} (DXY context: {dxy_symbol if dxy_symbol else 'N/A'})")
    if active_trade_details and active_trade_details["status"] == "OPEN":
        print(f"  Active trade: {active_trade_details['direction']} {actif_primaire_symbol} @{active_trade_details['entry']:.5f} SL:{active_trade_details['sl']:.5f} TP:{active_trade_details['tp']:.5f}")
    try:
        img_primaire = Image.open(chemin_image_primaire)
        img_dxy = Image.open(chemin_image_dxy) if chemin_image_dxy and os.path.exists(chemin_image_dxy) else None
        prompt_parts = [f"MISE À JOUR GRAPHIQUE : {actif_primaire_symbol} " + (f"ET {dxy_symbol} " if dxy_symbol else "") + f"- TIMEFRAME {timeframe_actuel}m."]
        prompt_parts.append("Référez-vous IMPÉRATIVEMENT à l'analyse initiale HTF et au PDF (si fourni).")
        if active_trade_details and active_trade_details["status"] == "OPEN":
            prompt_parts.extend([
                f"\n**GESTION DE TRADE EN COURS POUR {actif_primaire_symbol} :**",
                # ... (instructions de gestion de trade comme avant)
            ])
        else:
            prompt_parts.extend([
                f"**RECHERCHE D'OPPORTUNITÉ DE TRADE POUR {actif_primaire_symbol} :**",
                # ... (instructions de recherche de trade comme avant)
            ])
        prompt_parts.append(f"\nGraphique actuel {actif_primaire_symbol} {timeframe_actuel}m :"); prompt_parts.append(img_primaire)
        if img_dxy:
             prompt_parts.extend([f"\nGraphique actuel {dxy_symbol} {timeframe_actuel}m :", img_dxy])
        elif dxy_symbol:
            prompt_parts.append(f"\nNote: Le graphique {dxy_symbol} {timeframe_actuel}m n'a pas pu être chargé.")
        if active_trade_details and active_trade_details["status"] == "OPEN":
            prompt_parts.append(f"""
            \n**Format de Réponse CONCIS pour la GESTION DE TRADE sur {actif_primaire_symbol}:**
            1.  **STATUT DU TRADE :** ...
            2.  **ACTION RECOMMANDÉE :** ...
            3.  **OBSERVATIONS CLÉS (ICT) :** ...
            """) # Prompts détaillés omis pour la concision
        else:
            prompt_parts.append(f"""
            \n**Format de Réponse CONCIS pour une NOUVELLE ENTRÉE sur {actif_primaire_symbol}:**
            1.  Si une entrée est confirmée ... `TRADE CONFIRME: [LONG/SHORT] {actif_primaire_symbol}.` ...
            2.  Si une entrée est IMMINENTE ... `ATTENDRE CONFIRMATION {actif_primaire_symbol}.` ...
            3.  Si le scénario envisagé est INVALIDÉ ... `INVALIDATION DU SCÉNARIO [LONG/SHORT] {actif_primaire_symbol}.` ...
            4.  Si aucune des situations ... `OBSERVATION ({actif_primaire_symbol} / {dxy_symbol if dxy_symbol else 'N/A'}) :` ...
            """) # Prompts détaillés omis pour la concision
        response = send_message_to_gemini_with_retry(chat, prompt_parts, f"Analyse Monitoring {timeframe_actuel}m {actif_primaire_symbol}")
        print(f"Gemini {timeframe_actuel}m: {response.text}")
        return response.text
    except Exception as e:
        print(f"Erreur analyse screenshot {timeframe_actuel}m: {e}")
        return f"Error during {timeframe_actuel}m analysis: {e}"

# --- Main Execution Block ---
if __name__ == "__main__":
    reset_environnement()
    pdf_file_path = trouver_pdfs()
    if not pdf_file_path: print("WARNING: No PDF found.")

    print("Initializing Gemini session...")
    try: chat_session = initialiser_session_gemini()
    except Exception as e: print(f"Failed to initialize Gemini session: {e}. Exiting."); exit()

    print("Capturing initial HTF screenshots...")
    chemins_images_init_dict = {"primary": [], "context": []}
    initial_screenshots_ok = True
    primary_asset_to_analyze = actifs[0]
    dxy_asset_to_analyze = CONTEXT_ASSETS[0] if CONTEXT_ASSETS else None

    print(f"\n--- Capturing HTF for Primary Asset: {primary_asset_to_analyze} ---")
    for tf in timeframes_init:
        path = prendre_screenshot_tradingview(primary_asset_to_analyze, tf)
        if path: chemins_images_init_dict["primary"].append(path)
        else: print(f"ERROR: Failed capture for {primary_asset_to_analyze} {tf}."); initial_screenshots_ok = False
        time.sleep(5)
    if dxy_asset_to_analyze:
        print(f"\n--- Capturing HTF for Context Asset: {dxy_asset_to_analyze} ---")
        for tf in timeframes_init:
            path = prendre_screenshot_tradingview(dxy_asset_to_analyze, tf)
            if path: chemins_images_init_dict["context"].append(path)
            else: print(f"Warning: Failed DXY capture {dxy_asset_to_analyze} {tf}.")
            time.sleep(5)

    if not initial_screenshots_ok or not chemins_images_init_dict["primary"]:
        print("ERROR: Critical initial screenshots failed. Exiting."); exit()

    if not envoyer_analyse_initiale(chat_session, chemins_images_init_dict, pdf_file_path, primary_asset_to_analyze, [dxy_asset_to_analyze] if dxy_asset_to_analyze else []):
        print("Exiting due to failure in initial analysis."); exit()

    print("Cleaning up initial HTF screenshots...")
    for asset_type in chemins_images_init_dict:
        for img_p in chemins_images_init_dict[asset_type]:
            if os.path.exists(img_p): os.remove(img_p)

    active_trade_info = None
    analysis_cycles_count = 0
    max_analysis_cycles = 60

    print(f"\n--- Starting Monitoring Loop for {primary_asset_to_analyze} (Context: {dxy_asset_to_analyze if dxy_asset_to_analyze else 'None'}) (max {max_analysis_cycles} cycles) ---")

    while analysis_cycles_count < max_analysis_cycles:
        analysis_cycles_count += 1
        current_time_str = time.strftime('%Y-%m-%d %H:%M:%S')
        trade_status_message = ""
        if active_trade_info and active_trade_info["status"] == "OPEN":
            trade_status_message = f"(MANAGING: {active_trade_info['direction']} {active_trade_info['asset']} E:{active_trade_info['entry']:.5f} SL:{active_trade_info['sl']:.5f} TP:{active_trade_info['tp']:.5f})"
        elif active_trade_info: # Trade closed
             trade_status_message = f"(PREVIOUS TRADE {active_trade_info['asset']} CLOSED: {active_trade_info['status']}. LOOKING FOR NEW ENTRY)"
             active_trade_info = None

        print(f"\nMonitoring Cycle #{analysis_cycles_count}/{max_analysis_cycles} for {primary_asset_to_analyze} - {current_time_str} {trade_status_message}")

        for tf_monitor in timeframes_monitor:
            if active_trade_info and active_trade_info["status"] != "OPEN": active_trade_info = None # Reset for new trade search

            print(f"-- Capturing and analyzing {primary_asset_to_analyze} " + (f"and {dxy_asset_to_analyze} " if dxy_asset_to_analyze else "") + f"{tf_monitor}m --")
            
            path_primary = prendre_screenshot_tradingview(primary_asset_to_analyze, tf_monitor)
            time.sleep(3)
            path_dxy = prendre_screenshot_tradingview(dxy_asset_to_analyze, tf_monitor) if dxy_asset_to_analyze else None

            if path_primary:
                analysis_text = analyser_screenshot_monitoring(
                    chat_session, path_primary, path_dxy, tf_monitor,
                    primary_asset_to_analyze, dxy_asset_to_analyze, active_trade_info
                )
                if analysis_text and "ERROR" not in analysis_text.upper():
                    if active_trade_info and active_trade_info["status"] == "OPEN":
                        updates = extract_trade_management_updates(analysis_text, active_trade_info)
                        if updates["action"] == "AJUSTER":
                            # (logique de mise à jour du trade comme avant)
                            prev_sl = active_trade_info["sl"]; prev_tp = active_trade_info["tp"]
                            active_trade_info["sl"] = updates.get("new_sl", prev_sl)
                            active_trade_info["tp"] = updates.get("new_tp", prev_tp)
                            print(f"TRADE UPDATE: {active_trade_info['asset']} SL {prev_sl:.5f}->{active_trade_info['sl']:.5f}, TP {prev_tp:.5f}->{active_trade_info['tp']:.5f}. Just: {updates.get('justification', 'N/A')}")
                        elif updates["action"] == "CLOTURER":
                            active_trade_info["status"] = f"CLOSED ({updates.get('reason', 'Gemini')})"
                            print(f"!!! TRADE CLOSED: {active_trade_info['asset']} - {active_trade_info['status']} !!!\nDetails: {analysis_text}\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                        else: # MAINTENIR
                            print(f"TRADE MAINTAINED: {active_trade_info['asset']}. Gemini: {(analysis_text.split('JUSTIFICATION :')[-1].strip() if 'JUSTIFICATION :' in analysis_text else analysis_text.splitlines()[0])}")
                    elif not active_trade_info: # Chercher nouveau trade
                        if "TRADE CONFIRME" in analysis_text.upper():
                            new_trade = extract_trade_parameters(analysis_text)
                            if new_trade:
                                active_trade_info = {"asset": primary_asset_to_analyze, **new_trade}
                                print(f"!!! NEW TRADE CONFIRMED: {active_trade_info['direction']} {active_trade_info['asset']} !!!\nE:{active_trade_info['entry']:.5f} SL:{active_trade_info['sl']:.5f} TP:{active_trade_info['tp']:.5f}\nReason: {analysis_text}\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                            else:
                                print(f"WARNING: 'TRADE CONFIRME' found, but params not parsed. Gemini: {analysis_text}")
                if os.path.exists(path_primary): os.remove(path_primary)
                if path_dxy and os.path.exists(path_dxy): os.remove(path_dxy)
            else:
                print(f"Failed to capture {tf_monitor}m for {primary_asset_to_analyze}. DXY: {'OK' if path_dxy else ('Fail/Skip' if dxy_asset_to_analyze else 'N/A')}")
            
            if tf_monitor != timeframes_monitor[-1]:
                print(f"Waiting 10s before next TF monitor ({primary_asset_to_analyze})...")
                time.sleep(10)

        if analysis_cycles_count < max_analysis_cycles:
            wait_inter_cycle = 30 if (active_trade_info and active_trade_info["status"] == "OPEN") else 60
            print(f"--- End Cycle #{analysis_cycles_count}. Wait {wait_inter_cycle}s for next... ---")
            time.sleep(wait_inter_cycle)

    # Conclusion
    if active_trade_info and active_trade_info["status"] == "OPEN":
        print(f"\nProcess finished: Max cycles reached. Trade OPEN: {active_trade_info}")
    elif analysis_cycles_count >= max_analysis_cycles:
        print(f"\nProcess finished: Max cycles reached. No trade active or last closed.")
    else:
        print(f"\nProcess finished: Loop exited.")
