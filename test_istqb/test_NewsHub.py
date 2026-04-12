import os
import time

import pytest
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


BASE_URL = os.getenv("NEWHUB_BASE_URL", "http://localhost:4200")
API_URL = os.getenv("NEWHUB_API_URL", "http://127.0.0.1:8000")

TEST_EMAIL = os.getenv("NEWHUB_TEST_EMAIL", "rayenbenyahmed02@gmail.com")
TEST_PASSWORD = os.getenv("NEWHUB_TEST_PASSWORD", "rayen2026")
TEST_FULLNAME = os.getenv("NEWHUB_TEST_FULLNAME", "rayen ben yahmed") 
STEP_PAUSE_SECONDS = 1


def log_test_start(name):
    print(f"\n===== TEST START: {name} =====")


def log_test_end(name):
    print(f"===== TEST END: {name} (PASS) =====")


def log_case(name):
    print(f"\n[CASE] {name}")


def log_step(message):
    print(f"[STEP] {message}")


def log_info(message):
    print(f"[INFO] {message}")


def log_check(message):
    print(f"[CHECK] {message}")


def wait_for(driver, condition, timeout=20):
    return WebDriverWait(driver, timeout).until(condition)


def pause_step():
    time.sleep(STEP_PAUSE_SECONDS)


def safe_click(driver, element, label):
    log_step(f"Cliquer sur {label}")
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    pause_step()

    try:
        element.click()
    except Exception:
        log_info(f"Click Selenium intercepté pour {label}, fallback JS click")
        driver.execute_script("arguments[0].click();", element)

    pause_step()


def wait_until_url_contains(driver, expected_text, timeout=20):
    start = time.time()
    while time.time() - start < timeout:
        if expected_text in driver.current_url:
            return True
        time.sleep(0.2)
    return False


def wait_until_save_state(driver, expected_saved, timeout=20):
    start = time.time()
    while time.time() - start < timeout:
        current_state = get_save_button_state(driver)
        if current_state == expected_saved:
            return True
        time.sleep(0.2)
    return False


@pytest.fixture(scope="session")
def driver():
    # Ignore legacy chromedriver in PATH to avoid version mismatch with browser.
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


@pytest.fixture(scope="session")
def test_user():
    # 1) S'assurer que l'utilisateur existe (idempotent)
    register_resp = requests.post(
        f"{API_URL}/register",
        data={
            "full_name": TEST_FULLNAME,
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
        timeout=10,
    )
    if register_resp.status_code not in (200, 400):
        pytest.fail(f"Echec préparation user test: {register_resp.status_code} {register_resp.text}")

    # 2) Récupérer l'id user via login API
    login_resp = requests.post(
        f"{API_URL}/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=10,
    )
    if login_resp.status_code != 200:
        pytest.fail(f"Echec login API user test: {login_resp.status_code} {login_resp.text}")

    user = login_resp.json().get("user", {})
    user_id = user.get("id")
    if not user_id:
        pytest.fail("Impossible de récupérer user.id depuis /login")

    return {"id": user_id, "email": TEST_EMAIL, "password": TEST_PASSWORD}


def clear_front_session(driver):
    log_step("Ouvrir la home pour nettoyer la session")
    driver.get(BASE_URL)
    pause_step()
    log_step("localStorage.clear()")
    driver.execute_script("window.localStorage.clear();")
    pause_step()
    log_step("sessionStorage.clear()")
    driver.execute_script("window.sessionStorage.clear();")
    pause_step()
    log_step("delete_all_cookies()")
    driver.delete_all_cookies()
    pause_step()


def open_first_article_details(driver):
    log_step("Ouvrir la home page")
    driver.get(BASE_URL)
    pause_step()

    log_step("Cliquer sur le premier article")
    first_card_link = wait_for(
        driver,
        EC.element_to_be_clickable((By.CSS_SELECTOR, "app-news-card article.news-card a")),
    )
    first_card_link.click()
    pause_step()

    log_step("Attendre l'affichage de la page details")
    wait_for(driver, EC.presence_of_element_located((By.CSS_SELECTOR, "article.details-card")))
    pause_step()

    details_url = driver.current_url
    source_url = driver.find_element(By.CSS_SELECTOR, "a.source-btn").get_attribute("href")
    if not source_url:
        pytest.fail("URL source article introuvable sur la page détails")

    log_info(f"details_url = {details_url}")
    log_info(f"article source_url = {source_url}")

    return details_url, source_url


def ensure_not_favorite(user_id, article_url):
    # Nettoyage défensif avant test
    log_step(f"Nettoyer l'état favori user={user_id}")
    requests.delete(
        f"{API_URL}/favorites",
        json={"user_id": user_id, "article_url": article_url},
        timeout=10,
    )
    pause_step()

    # Vérification état non favori
    status_resp = requests.get(
        f"{API_URL}/favorites-status",
        params={"user_id": user_id, "article_url": article_url},
        timeout=10,
    )
    assert status_resp.status_code == 200, status_resp.text
    assert status_resp.json().get("saved") is False
    log_check("Favori initial = False")


def is_favorite(user_id, article_url):
    resp = requests.get(
        f"{API_URL}/favorites-status",
        params={"user_id": user_id, "article_url": article_url},
        timeout=10,
    )
    assert resp.status_code == 200, resp.text
    saved = resp.json().get("saved") is True
    log_check(f"favorites-status => saved={saved}")
    return saved


def login_from_ui(driver, email, password):
    log_step("Remplir le formulaire login")
    email_input = wait_for(driver, EC.presence_of_element_located((By.NAME, "email")))
    password_input = wait_for(driver, EC.presence_of_element_located((By.NAME, "password")))
    pause_step()

    email_input.clear()
    email_input.send_keys(email)
    password_input.clear()
    password_input.send_keys(password)
    pause_step()

    sign_in_btn = wait_for(
        driver,
        EC.element_to_be_clickable((By.XPATH, "//button[@type='submit' and contains(., 'Sign in')]")),
    )
    log_step("Cliquer sur Sign in")
    sign_in_btn.click()
    pause_step()


def get_save_button_state(driver):
    label = driver.find_element(By.CSS_SELECTOR, "button.save-btn").text.strip().lower()
    saved = "saved" in label and "save article" not in label
    log_check(f"Etat bouton save => label='{label}' saved={saved}")
    return saved


def wait_until_comment_present(driver, comment_text, timeout=20):
    start = time.time()
    while time.time() - start < timeout:
        body_text = driver.find_element(By.TAG_NAME, "body").text
        if comment_text in body_text:
            return True
        time.sleep(0.2)
    return False


def is_comment_present_api(article_url, comment_text):
    resp = requests.get(
        f"{API_URL}/comments",
        params={"article_url": article_url},
        timeout=10,
    )
    assert resp.status_code == 200, resp.text

    comments = resp.json()
    index = 0
    while index < len(comments):
        if comment_text in comments[index].get("comment_content", ""):
            log_check("Commentaire trouvé via API")
            return True
        index += 1

    log_check("Commentaire non trouvé via API")
    return False


def test_go_to_source(driver):
    log_test_start("test_go_to_source")
    clear_front_session(driver)
    _, source_url = open_first_article_details(driver)

    source_btn = wait_for(driver, EC.presence_of_element_located((By.CSS_SELECTOR, "a.source-btn")))
    href = source_btn.get_attribute("href")
    log_info(f"source href = {href}")
    assert href == source_url
    pause_step()

    old_handles = driver.window_handles
    safe_click(driver, source_btn, "le bouton source")

    opened_new_tab = False
    start = time.time()
    while time.time() - start < 10:
        current_handles = driver.window_handles
        if len(current_handles) > len(old_handles):
            opened_new_tab = True
            break
        time.sleep(0.2)

    assert opened_new_tab is True
    pause_step()

    new_handle = None
    index = 0
    current_handles = driver.window_handles
    while index < len(current_handles):
        handle = current_handles[index]
        found = False
        j = 0
        while j < len(old_handles):
            if handle == old_handles[j]:
                found = True
                break
            j += 1
        if not found:
            new_handle = handle
            break
        index += 1

    assert new_handle is not None
    driver.switch_to.window(new_handle)
    pause_step()
    log_check(f"Nouvelle URL ouverte = {driver.current_url}")
    assert driver.current_url.startswith("http")

    driver.close()
    pause_step()
    driver.switch_to.window(old_handles[0])
    pause_step()
    log_test_end("test_go_to_source")


def test_add_comment(driver, test_user):
    log_test_start("test_add_comment")
    user_id = test_user["id"]

    clear_front_session(driver)
    _, article_url = open_first_article_details(driver)

    log_case("Commentaire sans login")
    comment_box = wait_for(driver, EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Post Comment')]")))
    safe_click(driver, comment_box, "Post Comment sans login")

    redirected_to_login = wait_until_url_contains(driver, "/login")
    assert redirected_to_login is True
    pause_step()
    assert "returnUrl=" in driver.current_url
    pause_step()

    log_case("Connexion puis retour details")
    login_from_ui(driver, test_user["email"], test_user["password"])

    returned_to_details = wait_until_url_contains(driver, "/details/")
    assert returned_to_details is True
    pause_step()

    log_case("Commentaire vide")
    textarea = wait_for(driver, EC.presence_of_element_located((By.CSS_SELECTOR, "textarea.comment-input")))
    textarea.clear()
    pause_step()
    post_btn = wait_for(driver, EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Post Comment')]")))
    log_step("Cliquer Post Comment avec champ vide")
    safe_click(driver, post_btn, "Post Comment avec champ vide")

    error_found = False
    start = time.time()
    while time.time() - start < 10:
        page_text = driver.find_element(By.TAG_NAME, "body").text
        if "Write a comment before posting." in page_text:
            error_found = True
            break
        time.sleep(0.2)

    assert error_found is True
    pause_step()

    log_case("Commentaire rempli")
    unique_comment = f"ISTQB comment {int(time.time())}"
    textarea.clear()
    textarea.send_keys(unique_comment)
    pause_step()
    log_step(f"Saisir le commentaire: {unique_comment}")
    post_btn = wait_for(driver, EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Post Comment')]")))
    safe_click(driver, post_btn, "Post Comment avec commentaire rempli")

    added_in_ui = wait_until_comment_present(driver, unique_comment)
    assert added_in_ui is True
    pause_step()

    added_in_api = is_comment_present_api(article_url, unique_comment)
    assert added_in_api is True
    pause_step()

    log_test_end("test_add_comment")


def test_save_news(driver, test_user):
    """
    Cas non connecté:
    1) Cliquer Save Article
    2) Vérifier redirection /login + returnUrl
    3) Vérifier aucun favori créé tant que login non fait

    Cas connecté:
    1) Login depuis /login
    2) Retour sur la page détail initiale
    3) Cliquer Save Article
    4) Vérifier bouton => Saved
    5) Re-cliquer pour unsave => Save Article
    """

    log_test_start("test_save_news")
    log_info(f"user test email={test_user['email']} id={test_user['id']}")
    user_id = test_user["id"]

    clear_front_session(driver)
    initial_details_url, article_url = open_first_article_details(driver)

    ensure_not_favorite(user_id, article_url)

    log_case("Non connecté")
    # Cas non connecté
    save_btn = wait_for(driver, EC.element_to_be_clickable((By.CSS_SELECTOR, "button.save-btn")))
    assert "save article" in save_btn.text.strip().lower()
    pause_step()
    log_step("Cliquer Save Article (guest)")
    safe_click(driver, save_btn, "Save Article guest")
    pause_step()

    redirected_to_login = wait_until_url_contains(driver, "/login")
    assert redirected_to_login is True
    pause_step()
    log_check(f"URL après clic guest save = {driver.current_url}")
    assert "returnUrl=" in driver.current_url
    pause_step()
    assert is_favorite(user_id, article_url) is False
    pause_step()

    log_case("Visiteur se connecte")
    # Cas visiteur qui se connecte
    login_from_ui(driver, test_user["email"], test_user["password"])

    returned_to_details = wait_until_url_contains(driver, "/details/")
    assert returned_to_details is True
    pause_step()
    log_check(f"URL après login = {driver.current_url}")
    assert "/details/" in driver.current_url
    # même page cible (au moins même route détail)
    assert driver.current_url.split("?")[0] == initial_details_url.split("?")[0]
    pause_step()

    # 3) Cliquer Save Article si l'article n'est pas déjà Saved
    save_btn = wait_for(driver, EC.element_to_be_clickable((By.CSS_SELECTOR, "button.save-btn")))
    if not get_save_button_state(driver):
        log_step("Cliquer Save Article (connecté)")
        safe_click(driver, save_btn, "Save Article connecté")
        pause_step()
    else:
        log_info("Article déjà Saved après retour login (auto-save)")

    # 4) Vérifier état Saved (auto-save ou clic manuel)
    is_saved_now = wait_until_save_state(driver, True)
    assert is_saved_now is True
    pause_step()
    assert is_favorite(user_id, article_url) is True
    pause_step()

    # 5) Re-cliquer pour désenregistrer
    save_btn = wait_for(driver, EC.element_to_be_clickable((By.CSS_SELECTOR, "button.save-btn")))
    safe_click(driver, save_btn, "désenregistrement")

    is_unsaved_now = wait_until_save_state(driver, False)
    assert is_unsaved_now is True
    pause_step()
    assert is_favorite(user_id, article_url) is False
    log_test_end("test_save_news")