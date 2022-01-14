from fileManager import FileManager
from logger import LogController
import os
import subprocess
import sys

from django.core.management.utils import get_random_secret_key


class CiUtils(object):

    def init_ci(self, path, is_local):
        self.logger = LogController()
        self.fileManager = FileManager(path)
        if not is_local:
            self.logger.header('generating env file...')
            self.ENV_FILE = self.get_env_content()
            self.fileManager.write_str(self.ENV_FILE)
            self.logger.greenText(f'Env file:\n{self.ENV_FILE}')
        else:
            self.logger.greenText('Running with env file local')

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
        return env

    def execute(self, command, is_printing=False):
        os.chdir(os.getcwd())
        self.logger.blueText(command)
        try:
            command_output = subprocess.check_output(command, shell=True).decode('utf-8')
            self.logger.success()
            if is_printing:
                self.logger.coloredText(command_output)
            res = 0
        except subprocess.CalledProcessError as e:
            res = 1
            self.logger.fail(e.stdout.decode("utf-8").replace("\n", "\n ").strip())
        return res

    def run_ci(self, path, is_local:bool):
        self.init_ci(path, is_local)
        ok = self.execute('python manage.py collectstatic --noinput', False)
        ok += self.execute('flake8 connect/', False)
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
    ci.run_ci(os.getcwd() + '/.env', len(sys.argv) > 1 and sys.argv[1] == 'local')
