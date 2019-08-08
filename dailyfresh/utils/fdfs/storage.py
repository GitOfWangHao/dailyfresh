from django.core.files.storage import Storage
from fdfs_client.client import Fdfs_client



class FDFSStorage(Storage):

    def _open(self, name, mode='rb'):
        """打开文件时使用"""
        pass

    def _save(self, name, content):
        """存储文件时使用"""
        # name :上传文件名
        # content: 包含上传文件内容的File对象-----读取文件内容

        # 创建一个Fast dfs 对象
        client = Fdfs_client('./utils/fdfs/client.conf')

        # 上传文件到Fast dfs系统中
        res = client.upload_appender_by_buffer(content.read())

        # return dict
        # {
        #     'Group name': group_name,
        #     'Remote file_id': remote_file_id,
        #     'Status': 'Upload successed.',
        #     'Local file name': '',
        #     'Uploaded size': upload_size,
        #     'Storage IP': storage_ip
        # }

        if res.get('Status') != 'Upload successed.':
            # 上传失败,抛出异常
            raise Exception('上传文件到fast dfs 失败')

        # 获取fast dfs存储的文件名
        filename = res.get('Remote file_id')

        return filename  # fast dfs 访问的url

    def exists(self, name):
        """django 判断文件名是否可用，在save之前判断,由于fast dfs 存储不存在重名问题，所以返回false"""
        return False

    def url(self, name):
        """返回访问文件的url路径"""

        return name
