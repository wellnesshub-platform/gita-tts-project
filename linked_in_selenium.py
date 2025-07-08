import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
import os

# 🔧 Configuration
LINKEDIN_EMAIL = "hshukla4@yahoo.com"
LINKEDIN_PASSWORD = "Walnut53!"
RESUME_PATH = os.path.abspath("resume-final.pdf")  # Change filename if needed

# Set up Chrome options
chrome_options = Options()
chrome_options.add_argument("--start-maximized")
# chrome_options.add_argument("--headless")  # Optional: run in headless mode

# Driver setup
driver = webdriver.Chrome(service=Service(), options=chrome_options)

try:
    print("🔐 Logging in to LinkedIn...")
    driver.get("https://www.linkedin.com/login")

    # Fill login form
    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "username"))).send_keys(LINKEDIN_EMAIL)
    driver.find_element(By.ID, "password").send_keys(LINKEDIN_PASSWORD)
    driver.find_element(By.XPATH, "//button[@type='submit']").click()

    print("✅ Logged in. Navigating to Job Application Settings...")
    driver.get("https://www.linkedin.com/jobs/application-settings/")

    # Wait for Upload Resume label
    upload_label = WebDriverWait(driver, 15).until(
        EC.element_to_be_clickable((By.XPATH, "//label[contains(., 'Upload resume')]"))
    )
    upload_label.click()
    time.sleep(2)

    # Reveal hidden file input
    print("🛠 Forcing input[type='file'] to be visible...")
    driver.execute_script("""
        const inputs = document.querySelectorAll("input[type='file']");
        for (const input of inputs) {
            input.style.display = 'block';
            input.style.visibility = 'visible';
        }
    """)
    time.sleep(1)

    # Upload resume
    print("📎 Locating file input and uploading...")
    file_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
    )
    file_input.send_keys(RESUME_PATH)
    print("✅ Resume uploaded successfully!")

except TimeoutException as te:
    print("❌ Timeout occurred:", te)
except Exception as e:
    print("❌ Unexpected error:", e)
finally:
    print("🧹 Cleaning up...")
    time.sleep(5)
    driver.quit()