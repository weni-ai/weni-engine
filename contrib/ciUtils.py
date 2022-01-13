from fileManager import FileManager
from logger import LogController
import os
import subprocess

from django.core.management.utils import get_random_secret_key


class CiUtils(object):

    def __init__(self):
        self.answers = ['SUCESS', 'FAILURE']

    def init_ci(self, path):
        self.logger = LogController()
        self.fileManager = FileManager(path)
        self.ENV_FILE = self.get_env_content()
        self.fileManager.write_str(self.ENV_FILE)

    def get_env_content(self):
        env = f"""
                ENGINE_PORT=8080
                SECRET_KEY=\"{get_random_secret_key()}\"
                OIDC_RP_REALM_NAME=""
                OIDC_RP_CLIENT_ID=""
                OIDC_OP_LOGOUT_ENDPOINT=""
                OIDC_RP_SCOPES=""
                OIDC_RP_CLIENT_SECRET=""
                OIDC_OP_TOKEN_ENDPOINT=""
                OIDC_OP_AUTHORIZATION_ENDPOINT=""
                OIDC_RP_SIGN_ALGO=""
                OIDC_RP_SERVER_URL=""
                OIDC_OP_USER_ENDPOINT=""
                OIDC_OP_JWKS_ENDPOINT=""
                BILLING_COST_PER_WHATSAPP=199
                BILLING_TEST_MODE=True
            """.replace(" ", "").strip()
        self.logger.log(0, f'env file created:\n{env}' + self.logger.logStyle[2])
        return env

    def execute(self, command, is_printing=False):
        os.chdir(os.getcwd())
        self.logger.log(2, 'Running\n' + self.logger.logStyle[2] + '└─' + command)
        try:
            command_output = subprocess.check_output(command, shell=True).decode('utf-8')
            self.logger.log(0, self.answers[0])
            if is_printing:
                self.logger.log(0, command_output)
            res = 0
        except subprocess.CalledProcessError as e:
            res = 1
            self.logger.log(res, self.answers[res])
            self.logger.log(res, e.stdout.decode("utf-8").replace("\n", "\n ").strip())
        return res

    def run_ci(self, path):
        self.init_ci(path)
        ok = self.execute('flake8 connect/', False)
        if self.execute('coverage run manage.py test --verbosity=2 --noinput', False) == 0:
            ok += self.execute('coverage report -m', True)
        else:
            ok += 1
        if ok > 0:
            exit(1)


if __name__ == '__main__':
    if not os.getcwd().endswith("weni-engine"):
        raise Exception("The command need be executed in weni-engine")
    ci = CiUtils()
    ci.run_ci(os.getcwd() + '/.env')
