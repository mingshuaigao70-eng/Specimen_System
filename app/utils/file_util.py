import os
import uuid
from flask import current_app
from werkzeug.datastructures import FileStorage

class FileHandler:
    """
    文件上传工具类
    支持：类型检查、大小限制、保存文件、自动生成唯一文件名
    """

    @staticmethod
    def allowed_file(filename: str) -> bool:
        """检查文件扩展名是否允许上传"""
        if '.' not in filename:
            return False
        ext = filename.rsplit('.', 1)[1].lower()
        return ext in current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif'})

    @staticmethod
    def generate_filename(original_filename: str) -> str:
        """生成唯一文件名，保留原始扩展名"""
        ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
        return f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex

    @staticmethod
    def save_file(file: FileStorage, folder_key: str, filename: str = None) -> str:
        """
        保存上传文件到指定目录
        :param file: FileStorage 对象
        :param folder_key: 配置中指定上传文件夹的 key，如 UPLOAD_FOLDER_IMAGES
        :param filename: 保存的文件名（不提供则自动生成唯一文件名）
        :return: 相对路径
        """
        upload_folder = current_app.config.get(folder_key)
        if not upload_folder:
            raise ValueError(f"配置中没有找到 {folder_key}")

        # 确保文件夹存在
        os.makedirs(upload_folder, exist_ok=True)

        # 文件名
        filename = filename or FileHandler.generate_filename(file.filename)
        file_path = os.path.join(upload_folder, filename)
        relative_path = os.path.join(os.path.basename(upload_folder), filename)

        # 保存文件
        file.save(file_path)
        return relative_path

    @staticmethod
    def check_file(file: FileStorage, max_size: int = None) -> bool:
        """
        检查文件是否符合条件（类型 + 大小）
        :param file: FileStorage 对象
        :param max_size: 最大文件大小（字节），默认为 config 的 MAX_CONTENT_LENGTH
        :return: bool
        """
        if not file:
            return False
        if not FileHandler.allowed_file(file.filename):
            return False

        max_bytes = max_size or current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)  # 回到文件开头
        return size <= max_bytes