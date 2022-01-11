class FileManager(object):

    def __init__(self, file_path):
        self.file_path = file_path

    def write_str(self, file_content):
        with open(self.file_path, "w") as file:
            try:
                file.writelines(file_content)
                return True
            except ValueError:
                return False
            finally:
                file.close()