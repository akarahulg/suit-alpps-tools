import json, os
import sys
import time
from copy import deepcopy
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import load_dotenv

load_dotenv()

class PriorityRunner:

    def __init__(self):
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        self.driver.maximize_window()
        self.wait = WebDriverWait(self.driver, 20)

    # -------------------------
    # Wait for page ready
    # -------------------------
    def wait_ready(self):
        self.wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(1)

    def resolve_env_variables(self, value):
        if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_key = value[2:-1]
            return os.getenv(env_key)
        return value
    # -------------------------
    # Element Finders
    # -------------------------
    def find_by_xpath(self, xpath):
        try:
            return self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        except:
            return None

    def find_by_id(self, element_id):
        try:
            if element_id == "None":
                return None

            if ":" in element_id:
                stable = element_id.split(":")[-1]
                xpath = f"//*[contains(@id, ':{stable}')]"
                return self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
            else:
                return self.wait.until(EC.element_to_be_clickable((By.ID, element_id)))
        except:
            return None

    def find_by_text(self, text):
        if text == "None":
            return None

        lowered = text.lower()

        elements = self.wait.until(
            EC.presence_of_all_elements_located(
                (By.XPATH, "//a | //button | //*[@role='button'] | //span")
            )
        )

        for el in elements:
            try:
                if lowered in el.text.strip().lower() and el.is_displayed():
                    return el
            except:
                continue

        return None

    # -------------------------
    # Actions
    # -------------------------
    def safe_click(self, element):
        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
        time.sleep(0.5)
        self.driver.execute_script("window.scrollBy(0,-120);")

        try:
            element.click()
        except:
            self.driver.execute_script("arguments[0].click();", element)

        self.wait_ready()

    def safe_input(self, element, value):
        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
        time.sleep(0.5)

        element.click()
        element.send_keys("\u0001")  # CTRL+A
        element.send_keys("\ue003")  # DELETE
        self.driver.execute_script("arguments[0].value = '';", element)

        element.send_keys(value)
        print(f"  ✅ Entered value: {value}")
        self.wait_ready()

    def select_dropdown(self, element, option_text):
        self.safe_click(element)
        time.sleep(0.5)

        options = self.wait.until(
            EC.presence_of_all_elements_located((By.XPATH, "//li"))
        )

        lowered = option_text.lower()

        for opt in options:
            try:
                if lowered in opt.text.strip().lower() and opt.is_displayed():
                    opt.click()
                    print(f"  ✅ Selected option: {option_text}")
                    self.wait_ready()
                    return
            except:
                continue

        print(f"  ❌ Option not found: {option_text}")

    def upload_file(self, file_path):
        print("🔎 Attempting upload...")

        try:
            self.wait.until(
                lambda d: len(d.find_elements(By.XPATH, "//input[@type='file']")) > 0
            )

            file_input = self.driver.find_element(By.XPATH, "//input[@type='file']")

            self.driver.execute_script("""
                arguments[0].style.display='block';
                arguments[0].style.visibility='visible';
                arguments[0].style.opacity=1;
            """, file_input)

            file_input.send_keys(file_path)
            print("  ✅ File path sent")

            self.wait.until(
                lambda d: len(d.find_elements(
                    By.XPATH,
                    "//button[contains(@id,'attachment-remove-button')]"
                )) > 0
            )

            print("  ✅ Upload confirmed")

        except Exception as e:
            print("  ❌ Upload failed:", e)

    # -------------------------
    # Confirmation
    # -------------------------
    def confirm_step(self, step):
        print("\n-----------------------------------")
        print("Approval Required For Step:")
        print(step)
        print("-----------------------------------")

        user_input = input("Proceed? (y/yes to continue): ").strip().lower()
        return user_input in ["y", "yes"]

    # -------------------------
    # Step Processor
    # -------------------------
    def process_step(self, step):

        if step.get("confirm", False):
            if not self.confirm_step(step):
                print("⛔ Step skipped.")
                return

        action = step.get("action")

        if action == "upload":
            self.upload_file(step["file"])
            return

        element = None

        if step.get("xpath"):
            element = self.find_by_xpath(step["xpath"])

        if not element and step.get("id"):
            element = self.find_by_id(step["id"])

        if not element and step.get("text"):
            element = self.find_by_text(step["text"])

        if not element:
            print("  ❌ Element not found.")
            return

        if action == "click":
            self.safe_click(element)

        elif action == "input":
            value = self.resolve_env_variables(step["value"])
            self.safe_input(element, value)

        elif action == "select":
            self.select_dropdown(element, step["option"])

    # -------------------------
    # Execute Workflow
    # -------------------------
    def execute(self, filename):

        with open(filename, "r") as f:
            workflow = json.load(f)

        self.driver.get("https://alpps.issdc.gov.in")
        self.wait_ready()

        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        if iframes:
            self.driver.switch_to.frame(iframes[0])

        for step in workflow:

            # 🔁 Handle repeat blocks
            if "repeat" in step and "steps" in step:

                repeat_count = step["repeat"]
                sub_steps = step["steps"]

                print(f"\n🔁 Repeating block {repeat_count} times")

                for i in range(repeat_count):
                    print(f"  ↪ Iteration {i}")

                    for sub_step in sub_steps:
                        step_copy = deepcopy(sub_step)

                        # Replace {index}
                        if step_copy.get("xpath"):
                            step_copy["xpath"] = step_copy["xpath"].replace("{index}", str(i))

                        if step_copy.get("id") and step_copy["id"] != "None":
                            step_copy["id"] = step_copy["id"].replace("{index}", str(i))

                        self.process_step(step_copy)

                continue

            # Normal step
            print(f"\nExecuting step: {step}")
            self.process_step(step)

        print("\n✅ Workflow Completed.")
        time.sleep(3)


# -------------------------
# CLI ENTRY
# -------------------------
if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage: python runner.py <workflow.json> [runs]")
        sys.exit(1)

    json_file = sys.argv[1]
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    print(f"Workflow File: {json_file}")
    print(f"Number of Runs: {runs}")

    for i in range(runs):
        print(f"\n========== RUN {i+1} of {runs} ==========")

        runner = PriorityRunner()
        runner.execute(json_file)
        runner.driver.quit()

    print("\n✅ All executions completed.")
