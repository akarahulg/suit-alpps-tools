import json
import os
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
import argparse

load_dotenv()


class PriorityRunner:

    def __init__(self):
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        self.driver.maximize_window()
        self.wait = WebDriverWait(self.driver, 20)
        self.runtime_data = {}

    # -------------------------
    # Wait for page ready
    # -------------------------
    def wait_ready(self):
        self.wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
        time.sleep(1)

    # -------------------------
    # Variable Resolver
    # -------------------------
    def resolve_variables(self, value):
        if not isinstance(value, str):
            return value
        if value.startswith("${") and value.endswith("}"):
            key = value[2:-1]
            if key in self.runtime_data:
                return str(self.runtime_data[key])
            env_value = os.getenv(key)
            if env_value is not None:
                return env_value
            raise Exception(f"❌ Variable '{key}' not found in data.json or .env")
        return value

    # -------------------------
    # Resolve variables inside step
    # -------------------------
    def resolve_step_variables(self, step):
        for field in ["value", "option", "file", "xpath", "id", "text"]:
            if field in step and step[field]:
                step[field] = self.resolve_variables(step[field])
        return step

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
        elements = self.wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, "//a | //button | //*[@role='button'] | //span")))
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
        options = self.wait.until(EC.presence_of_all_elements_located((By.XPATH, "//li")))
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
        file_path = self.resolve_variables(file_path)
        print("🔎 Attempting upload...")
        try:
            self.wait.until(lambda d: len(d.find_elements(By.XPATH, "//input[@type='file']")) > 0)
            file_input = self.driver.find_element(By.XPATH, "//input[@type='file']")
            self.driver.execute_script("""
                arguments[0].style.display='block';
                arguments[0].style.visibility='visible';
                arguments[0].style.opacity=1;
            """, file_input)
            file_input.send_keys(file_path)
            print("  ✅ File path sent")
            self.wait.until(lambda d: len(d.find_elements(
                By.XPATH, "//button[contains(@id,'attachment-remove-button')]")) > 0)
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
    # Process single step
    # -------------------------
    def process_step(self, step):
        step = self.resolve_step_variables(step)
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
            self.safe_input(element, step["value"])
        elif action == "select":
            self.select_dropdown(element, step["option"])

    # -------------------------
    # Execute Workflow
    # -------------------------
    def execute(self, workflow_file, data_file=None):
        with open(workflow_file, "r") as f:
            workflow = json.load(f)
        if data_file:
            with open(data_file, "r") as f:
                self.runtime_data = json.load(f)
        self.driver.get("https://alpps.issdc.gov.in")
        self.wait_ready()
        iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
        if iframes:
            self.driver.switch_to.frame(iframes[0])

        for step in workflow:

            # Normal repeat (no index)
            if "repeat" in step and "steps" in step:
                repeat_count = int(self.resolve_variables(step["repeat"]))
                print(f"\n🔁 Repeating block {repeat_count} times")
                for i in range(repeat_count):
                    for sub_step in step["steps"]:
                        step_copy = deepcopy(sub_step)
                        # Replace {index} if present
                        for key in ["xpath", "id", "value", "option", "file", "text"]:
                            if key in step_copy and isinstance(step_copy[key], str):
                                step_copy[key] = step_copy[key].replace("{index}", str(i))
                        self.process_step(step_copy)
                continue

            # Index repeat
            if "indexrepeat" in step and "steps" in step:
                repeat_count = int(self.resolve_variables(step["indexrepeat"]))
                print(f"\n🔁 Index repeating block {repeat_count} times")
                for i in range(repeat_count):
                    for sub_step in step["steps"]:
                        step_copy = deepcopy(sub_step)
                        # Replace {index} in all relevant fields
                        for key in ["xpath", "id", "value", "option", "file", "text"]:
                            if key in step_copy and isinstance(step_copy[key], str):
                                step_copy[key] = step_copy[key].replace("{index}", str(i))
                        self.process_step(step_copy)
                continue

            # Normal step
            print(f"\nExecuting step: {step}")
            self.process_step(step)

        print("\n✅ Workflow Completed.")
        time.sleep(3)


# -------------------------
# CLI ENTRY WITH ARGPARSE
# -------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ALPPS Bot")
    parser.add_argument("workflow", help="Workflow JSON file")
    parser.add_argument("data", help="Data JSON file with variable values")
    parser.add_argument("--runs", type=int, default=1, help="Number of times to run the workflow")
    args = parser.parse_args()

    for run in range(args.runs):
        print(f"\n========== RUN {run+1} of {args.runs} ==========")
        runner = PriorityRunner()
        runner.execute(args.workflow, args.data)
        runner.driver.quit()

    print("\n✅ All executions completed.")
