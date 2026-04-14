import os
import time

import pytest
import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.expected_conditions import element_to_be_clickable, presence_of_element_located
from selenium.webdriver.support.ui import WebDriverWait


BASE_URL = os.getenv("NEWHUB_BASE_URL", "http://localhost:4200")
API_URL = os.getenv("NEWHUB_API_URL", "http://127.0.0.1:8000")

TEST_EMAIL = os.getenv("NEWHUB_TEST_EMAIL", "rayenbenyahmed02@gmail.com")
TEST_PASSWORD = os.getenv("NEWHUB_TEST_PASSWORD", "rayen2026")
WAIT_TIMEOUT = 20


# Attend un element cliquable et force un echec pytest explicite en cas de timeout.
def wait_clickable_or_fail(driver, locator, label, timeout=WAIT_TIMEOUT):
    try:
        return WebDriverWait(driver, timeout).until(element_to_be_clickable(locator)) #driver sert a interagir m3a l navigateur, locator c est la methode de localisation (ex: By.CSS_SELECTOR) w label c est une description textuelle de l element pour les messages d erreur
    except TimeoutException:
        pytest.fail(f"Timeout {timeout}s: element clickable introuvable ({label}). URL actuelle: {driver.current_url}")


# Attend la presence d'un element dans le DOM et force un echec pytest explicite en cas de timeout.
def wait_present_or_fail(driver, locator, label, timeout=WAIT_TIMEOUT):
    try:
        return WebDriverWait(driver, timeout).until(presence_of_element_located(locator))
    except TimeoutException:
        pytest.fail(f"Timeout {timeout}s: element present introuvable ({label}). URL actuelle: {driver.current_url}")


@pytest.fixture(scope="session")   #Scope session pour éviter de relancer le driver à chaque test
# Initialise un seul navigateur Chrome pour toute la session de tests puis le ferme a la fin.
def driver(): 
    bad_driver_fragment = os.path.normcase("chromedriver-win64")
    path_entries = os.environ.get("PATH", "").split(os.pathsep)
    filtered_entries = []
    for entry in path_entries:
        if bad_driver_fragment not in os.path.normcase(entry):
            filtered_entries.append(entry)
    os.environ["PATH"] = os.pathsep.join(filtered_entries)

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")
    drv = webdriver.Chrome(options=options)
    yield drv
    drv.quit()


# Verifie qu'un clic sur le bouton Source ouvre bien un nouvel onglet avec une URL valide.
def test_go_to_source(driver):
    print("\n test go to source start")
    
    # ------ nit2akdou ili local/session storage initialisé ------
    driver.get(BASE_URL) 
    """
    localStorage = persistant, partagé par les pages du même domaine
    sessionStorage = temporaire, limité à l’onglet acti
    """
    time.sleep(1)
    driver.execute_script("window.localStorage.clear();")
    time.sleep(1)
    driver.execute_script("window.sessionStorage.clear();") 
    time.sleep(1)

    driver.get(BASE_URL)
    time.sleep(1)

    
    #------ nod5lou l article details ------
    """
    element_to_be_clickable :yistana 20s hata ywali l element mawjoud(visible) + clicable => ylawj aala l article => yit2aked li howa clicable => yrajaa l element
    """
    # ylawj lien d article clicable 
    first_card_link = wait_clickable_or_fail(
        driver,
        (By.CSS_SELECTOR, "app-news-card article.news-card a"),
        "Lien de la premiere news card",
    )
    first_card_link.click()
    time.sleep(1)

    """
    presence_of_element_located : yistana 20s hata ywali l element mawjoud fi dom
    """
    # yit2aked ili lpage detail mawjouda (4ohrt)
    wait_present_or_fail(
        driver,
        (By.CSS_SELECTOR, "article.details-card"),
        "Carte details article",
    )
    time.sleep(1)


    #------ ntestiw source ------
    # yit2aked ili lbouton source mawjouda w yakhou href mte3ha
    source_btn = wait_present_or_fail(
        driver,
        (By.CSS_SELECTOR, "a.source-btn"),
        "Bouton source",
    )
    source_url = source_btn.get_attribute("href")

    #yiscroli hata twali bouton source fi centre taa l ecran
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", source_btn)  
    time.sleep(1)
    try:
        source_btn.click()
    except Exception:
        driver.execute_script("arguments[0].click();", source_btn)
    time.sleep(1)
    
    old_handles = driver.window_handles  #liste des onglets avant le clic

    """
    window_handles : liste des onglets/fenêtres ouverts
    bich nit2akdou ili onglet source t7alet ncompariw nb d onglet/fenetre kbal w baed lclic ken zed rw maaneha t7alt onglet jdida
    """
    start = time.time()  # ysajl l instant de depart
    while time.time() - start < 10:
        if len(driver.window_handles) > len(old_handles): 
            break
        time.sleep(0.2) 

    #nstokiw fi new_handle l onglet source (ynajmou ykounou akther min onglet)
    new_handle = None
    for handle in driver.window_handles:
        if handle not in old_handles:
            new_handle = handle
            break

    assert new_handle is not None, "onglet source non ouvert"  #transfrme un bug flous en msg de test clair “pas de nouvel onglet ouvert”.
    
    ##verifie que la nav ouvert une url valide et pas une page vide ou un echec d ouverture 
    driver.switch_to.window(new_handle)
    time.sleep(1)
    print(f"[CHECK] Nouvelle URL ouverte = {driver.current_url}")
    assert driver.current_url.startswith("http"), "La navigation n'a pas ouvert une url valide"  

    driver.close()
    time.sleep(1)
    driver.switch_to.window(old_handles[0])
    time.sleep(1)
    print("===== TEST END: test_go_to_source (PASS) =====")


# Couvre le parcours ajout de commentaire: guest redirige vers login puis utilisateur connecte poste un commentaire.
def test_add_comment(driver):
    print("\n===== TEST START: test_add_comment =====")
    # ------ nit2akdou ili local/session storage initialisé ------
    driver.get(BASE_URL)
    time.sleep(1)
    driver.execute_script("window.localStorage.clear();")
    time.sleep(1)
    driver.execute_script("window.sessionStorage.clear();")
    time.sleep(1)
    driver.delete_all_cookies()
    time.sleep(1)

    driver.get(BASE_URL)
    time.sleep(1)

    #------ nod5lou l article details ------
    first_card_link = wait_clickable_or_fail(
        driver,
        (By.CSS_SELECTOR, "app-news-card article.news-card a"),
        "Lien de la premiere news card",
    )
    first_card_link.click()
    time.sleep(1)

    wait_present_or_fail(
        driver,
        (By.CSS_SELECTOR, "article.details-card"),
        "Carte details article",
    )
    time.sleep(1)

    article_url = driver.find_element(By.CSS_SELECTOR, "a.source-btn").get_attribute("href")  # yakhou url mte3 article details bach ntestiw biha l api baed

    # 1) ---------- ntestiw commentaire en cas guest -----------
    print("\n[CASE] Commentaire sans login")
    comment_button = wait_clickable_or_fail(
        driver,
        (By.XPATH, "//button[contains(., 'Post Comment')]"),
        "Bouton Post Comment (guest)",
    )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", comment_button)
    time.sleep(1)
    try:
        comment_button.click()
    except Exception:
        driver.execute_script("arguments[0].click();", comment_button)
    time.sleep(1)

    start = time.time()
    while time.time() - start < 20:
        if "/login" in driver.current_url:
            break
        time.sleep(0.2)
        
    assert "/login" in driver.current_url, "Apres clic sur Post Comment en guest, la page de login n'est pas affichée"
    assert "returnUrl=" in driver.current_url, "l'url de retour n'est pas présente dans la page de login"
    time.sleep(1)
    
    print("\n[CASE] Connexion puis retour details")
    #remplissage du formulaire de login
    email_input = wait_present_or_fail(driver, (By.NAME, "email"), "Champ email login")
    password_input = wait_present_or_fail(driver, (By.NAME, "password"), "Champ password login")
    email_input.clear()
    email_input.send_keys(TEST_EMAIL)
    password_input.clear()
    password_input.send_keys(TEST_PASSWORD)
    time.sleep(1)

    sign_in_btn = wait_clickable_or_fail(
        driver,
        (By.XPATH, "//button[@type='submit' and contains(., 'Sign in')]"),
        "Bouton Sign in",
    )
    sign_in_btn.click()
    time.sleep(1)

    start = time.time()
    while time.time() - start < 20:
        if "/details/" in driver.current_url:
            break
        time.sleep(0.2)
    assert "/details/" in driver.current_url, "apres connexion, la page de details n'est pas affichée"
    time.sleep(1)

    # 2) ----------- ntestiw commentaire en cas user connecté --------------
    # -------cmnt vide ---------
    print("\n[CASE] Commentaire vide")
    textarea = wait_present_or_fail(
        driver,
        (By.CSS_SELECTOR, "textarea.comment-input"),
        "Textarea commentaire",
    )
    textarea.clear()
    time.sleep(1)
    comment_button = wait_clickable_or_fail(
        driver,
        (By.XPATH, "//button[contains(., 'Post Comment')]"),
        "Bouton Post Comment (commentaire vide)",
    )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", comment_button)
    time.sleep(1)
    try:
        comment_button.click()
    except Exception:
        driver.execute_script("arguments[0].click();", comment_button)
    time.sleep(1)

    error_found = False
    start = time.time()
    while time.time() - start < 10:
        if "Write a comment before posting." in driver.find_element(By.TAG_NAME, "body").text:
            error_found = True
            break
        time.sleep(0.2)
    assert error_found is True, "Aucun message d'erreur pour commentaire vide ou message d'erreur incorrect"
    time.sleep(1)

    #------- cmnt rempli ---------
    print("\n[CASE] Commentaire rempli")
    unique_comment = f"test commentaire {int(time.time())}"
    textarea.clear()
    textarea.send_keys(unique_comment)
    time.sleep(1)
    comment_button = wait_clickable_or_fail(
        driver,
        (By.XPATH, "//button[contains(., 'Post Comment')]"),
        "Bouton Post Comment (commentaire rempli)",
    )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", comment_button)
    time.sleep(1)
    try:
        comment_button.click()
    except Exception:
        driver.execute_script("arguments[0].click();", comment_button)
    time.sleep(1)

    start = time.time()
    while time.time() - start < 20:
        if unique_comment in driver.find_element(By.TAG_NAME, "body").text:
            break
        time.sleep(0.2)
    assert unique_comment in driver.find_element(By.TAG_NAME, "body").text
    time.sleep(1)

    comments_resp = requests.get( # yrecuperi les cmnts taa l article sous forme list en json par l api bach ntestiw ili cmnt ajouté est bien dans la liste retournée par l api
        f"{API_URL}/comments",
        params={"article_url": article_url},
        timeout=10,
    )
    assert comments_resp.status_code == 200, comments_resp.text
    found = False
    for comment in comments_resp.json():
        if unique_comment in comment.get("comment_content", ""):
            found = True
            break
    assert found is True, "Le commentaire ajouté n'est pas retourné par l'API" 
    time.sleep(1)

    print("===== TEST END: test_add_comment (PASS) =====")


# Verifie le cycle complet de favoris: guest -> login, sauvegarde, puis suppression du favori.
def test_save_news(driver):
    print("\n===== TEST START: test_save_news =====")

    driver.get(BASE_URL)
    time.sleep(1)
    driver.execute_script("window.localStorage.clear();")
    time.sleep(1)
    driver.execute_script("window.sessionStorage.clear();")
    time.sleep(1)
    driver.delete_all_cookies()
    time.sleep(1)

    driver.get(BASE_URL)
    time.sleep(1)

    first_card_link = wait_clickable_or_fail(
        driver,
        (By.CSS_SELECTOR, "app-news-card article.news-card a"),
        "Lien de la premiere news card",
    )
    first_card_link.click()
    time.sleep(1)

    wait_present_or_fail(
        driver,
        (By.CSS_SELECTOR, "article.details-card"),
        "Carte details article",
    )
    time.sleep(1)

    article_url = driver.find_element(By.CSS_SELECTOR, "a.source-btn").get_attribute("href")
    login_resp = requests.post(
        f"{API_URL}/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=10,
    )
    assert login_resp.status_code == 200, login_resp.text
    user_id = login_resp.json().get("user", {}).get("id")
    assert user_id is not None

    requests.delete(
        f"{API_URL}/favorites",
        json={"user_id": user_id, "article_url": article_url},
        timeout=10,
    )
    time.sleep(1)

    status_resp = requests.get(
        f"{API_URL}/favorites-status",
        params={"user_id": user_id, "article_url": article_url},
        timeout=10,
    )
    assert status_resp.status_code == 200, status_resp.text
    assert status_resp.json().get("saved") is False
    print("[CHECK] Favori initial = False")

    print("\n[CASE] Non connecté")
    save_button = wait_clickable_or_fail(
        driver,
        (By.CSS_SELECTOR, "button.save-btn"),
        "Bouton Save Article (guest)",
    )
    assert "save article" in save_button.text.strip().lower()
    time.sleep(1)
    print("[STEP] Cliquer Save Article (guest)")
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_button)
    time.sleep(1)
    try:
        save_button.click()
    except Exception:
        driver.execute_script("arguments[0].click();", save_button)
    time.sleep(1)

    start = time.time()
    while time.time() - start < 20:
        if "/login" in driver.current_url:
            break
        time.sleep(0.2)
    assert "/login" in driver.current_url
    assert "returnUrl=" in driver.current_url
    time.sleep(1)

    status_resp = requests.get(
        f"{API_URL}/favorites-status",
        params={"user_id": user_id, "article_url": article_url},
        timeout=10,
    )
    assert status_resp.status_code == 200, status_resp.text
    assert status_resp.json().get("saved") is False
    print(f"[CHECK] URL après clic guest save = {driver.current_url}")
    time.sleep(1)

    print("\n[CASE] Visiteur se connecte")
    email_input = wait_present_or_fail(driver, (By.NAME, "email"), "Champ email login")
    password_input = wait_present_or_fail(driver, (By.NAME, "password"), "Champ password login")
    email_input.clear()
    email_input.send_keys(TEST_EMAIL)
    password_input.clear()
    password_input.send_keys(TEST_PASSWORD)
    time.sleep(1)

    sign_in_btn = wait_clickable_or_fail(
        driver,
        (By.XPATH, "//button[@type='submit' and contains(., 'Sign in')]"),
        "Bouton Sign in",
    )
    sign_in_btn.click()
    time.sleep(1)

    start = time.time()
    while time.time() - start < 20:
        if "/details/" in driver.current_url:
            break
        time.sleep(0.2)
    assert "/details/" in driver.current_url
    print(f"[CHECK] URL après login = {driver.current_url}")
    time.sleep(1)

    save_button = wait_clickable_or_fail(
        driver,
        (By.CSS_SELECTOR, "button.save-btn"),
        "Bouton Save Article (connecte)",
    )
    if "saved" not in save_button.text.strip().lower():
        print("[STEP] Cliquer Save Article (connecté)")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_button)
        time.sleep(1)
        try:
            save_button.click()
        except Exception:
            driver.execute_script("arguments[0].click();", save_button)
        time.sleep(1)

    start = time.time()
    while time.time() - start < 20:
        if "saved" in driver.find_element(By.CSS_SELECTOR, "button.save-btn").text.strip().lower():
            break
        time.sleep(0.2)
    assert "saved" in driver.find_element(By.CSS_SELECTOR, "button.save-btn").text.strip().lower()
    time.sleep(1)

    status_resp = requests.get(
        f"{API_URL}/favorites-status",
        params={"user_id": user_id, "article_url": article_url},
        timeout=10,
    )
    assert status_resp.status_code == 200, status_resp.text
    assert status_resp.json().get("saved") is True
    time.sleep(1)

    save_button = wait_clickable_or_fail(
        driver,
        (By.CSS_SELECTOR, "button.save-btn"),
        "Bouton Save Article (desactivation)",
    )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", save_button)
    time.sleep(1)
    try:
        save_button.click()
    except Exception:
        driver.execute_script("arguments[0].click();", save_button)
    time.sleep(1)

    start = time.time()
    while time.time() - start < 20:
        if "save article" in driver.find_element(By.CSS_SELECTOR, "button.save-btn").text.strip().lower():
            break
        time.sleep(0.2)
    assert "save article" in driver.find_element(By.CSS_SELECTOR, "button.save-btn").text.strip().lower()
    time.sleep(1)

    status_resp = requests.get(
        f"{API_URL}/favorites-status",
        params={"user_id": user_id, "article_url": article_url},
        timeout=10,
    )
    assert status_resp.status_code == 200, status_resp.text
    assert status_resp.json().get("saved") is False

    print("===== TEST END: test_save_news (PASS) =====")