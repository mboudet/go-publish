import hashlib
import os
import shutil
from time import sleep

from . import GopublishTestCase

from gopublish.db_models import PublishedFile
from gopublish.extensions import db


class TestApiPublish(GopublishTestCase):

    template_repo = "/gopublish/test-data/test-repo/"
    testing_repos = ["/repos/myrepo", "/repos/myrepo_copy"]
    public_file = "/repos/myrepo/my_file_to_publish.txt"
    published_file = "/repos/myrepo/public/my_file_to_publish_v1.txt"
    file_id = ""

    def setup_method(self):
        for repo in self.testing_repos:
            if os.path.exists(repo):
                shutil.rmtree(repo)
            shutil.copytree(self.template_repo, repo)

    def teardown_method(self):
        for repo in self.testing_repos:
            if os.path.exists(repo):
                shutil.rmtree(repo)
        if self.file_id:
            for file in PublishedFile.query.filter(PublishedFile.id == self.file_id):
                db.session.delete(file)
            db.session.commit()
            self.file_id = ""
        if self.token_id:
            for token in PublishedFile.query.filter(Token.id == self.token_id):
                db.session.delete(token)
            db.session.commit()
            self.token_id = ""

    def test_publish_missing_body(self, client):
        """
        Publish without body
        """
        response = client.post('/api/publish')

        assert response.status_code == 400
        assert response.json == {'error': 'Missing body'}

    def test_publish_missing_token(self, client):
        """
        Publish without a token
        """
        data = {
            'files': '/foo/bar'
        }
        response = client.post('/api/publish', json=data)
        assert response.status_code == 401
        assert response.json == {'error': 'Missing token in body'}

    def test_publish_expired_token(self, client):
        """
        Publish without a token
        """
        self.token_id = self.create_mock_token(expire_now=True)
        data = {
            'token': self.token_id,
            'files': '/foo/bar'
        }
        response = client.post('/api/publish', json=data)
        assert response.status_code == 401
        assert response.json == {'error': 'Missing token in body'}

    def test_publish_missing_path(self, client):
        """
        Publish without a proper path
        """
        self.token_id = self.create_mock_token()
        data = {
            'token': self.token_id,
            'files': "/foo/bar"
        }
        response = client.post('/api/publish', json=data)

        assert response.status_code == 400
        assert response.json == {'error': 'Missing path'}

    def test_publish_missing_file(self, client):
        """
        Publish a missing file
        """
        self.token_id = self.create_mock_token()
        data = {
            'token': self.token_id,
            'path': "/foo/bar"
        }
        response = client.post('/api/publish', json=data)

        assert response.status_code == 400
        assert response.json == {'error': 'File not found at path /foo/bar'}

    def test_publish_folder(self, client):
        """
        Publish a folder
        """
        self.token_id = self.create_mock_token()
        path_to_folder = "/repos/myrepo/myfolder"
        os.mkdir(path_to_folder)

        data = {
            'token': self.token_id,
            'path': path_to_folder
        }
        response = client.post('/api/publish', json=data)

        assert response.status_code == 400
        assert response.json == {'error': 'Path must not be a folder or a symlink'}

    def test_publish_symlink(self, client):
        """
        Publish a symlink
        """
        self.token_id = self.create_mock_token()
        symlink_path = "/repos/myrepo/mylink"
        os.symlink(self.public_file, symlink_path)

        data = {
            'token': self.token_id,
            'path': symlink_path
        }
        response = client.post('/api/publish', json=data)

        assert response.status_code == 400
        assert response.json == {'error': 'Path must not be a folder or a symlink'}

    def test_publish_incorrect_version(self, client):
        """
        Publish without a proper version
        """
        self.token_id = self.create_mock_token()
        data = {
            'token': self.token_id,
            'path': self.public_file,
            'version': "x"
        }
        response = client.post('/api/publish', json=data)

        assert response.status_code == 400
        assert response.json == {'error': "Value x is not an integer > 0"}

    def test_publish_duplicate_version(self, client):
        """
        Publish a duplicate (file and version)
        """
        self.token_id = self.create_mock_token()
        data = {
            'token': self.token_id,
            'path': self.public_file,
            'version': "2"
        }
        response = client.post('/api/publish', json=data)

        assert response.status_code == 400
        assert response.json == {'error': "Error checking file : File is already published in that version"}

    def test_publish_wrong_email(self, client):
        """
        Publish with wrong email address
        """
        self.token_id = self.create_mock_token()
        data = {
            'token': self.token_id,
            'path': self.public_file,
            'email': 'x'
        }
        response = client.post('/api/publish', json=data)

        assert response.status_code == 400
        assert response.json == {"error": "The email address is not valid. It must have exactly one @-sign."}

    def test_publish_wrong_contact(self, client):
        """
        Publish with wrong email address
        """
        self.token_id = self.create_mock_token()
        data = {
            'token': self.token_id,
            'path': self.public_file,
            'contact': 'x'
        }
        response = client.post('/api/publish', json=data)

        assert response.status_code == 400
        assert response.json == {"error": "The email address is not valid. It must have exactly one @-sign."}

    def test_publish_link_success(self, app, client):
        """
        Try to publish a file in normal conditions
        """
        self.token_id = self.create_mock_token()
        public_file = "/repos/myrepo/my_file_to_publish.txt"
        published_file = "/repos/myrepo/public/my_file_to_publish_v1.txt"

        data = {
            'token': self.token_id,
            'path': public_file,
        }
        response = client.post('/api/publish', json=data)

        assert response.status_code == 200
        data = response.json
        assert data['message'] == "File registering. It should be ready soon"
        assert 'file_id' in data

        self.file_id = data['file_id']

        wait = 0
        while wait < 60:
            sleep(2)

            if os.path.exists(published_file):
                break
            wait += 1

        assert os.path.exists(published_file)
        assert os.path.islink(public_file)
        assert os.readlink(public_file) == published_file

    def test_publish_copy_success(self, app, client):
        """
        Try to publish a file in normal conditions
        """
        self.token_id = self.create_mock_token()
        public_file = "/repos/myrepo_copy/my_file_to_publish.txt"
        published_file = "/repos/myrepo_copy/public/my_file_to_publish_v1.txt"

        data = {
            'token': self.token_id,
            'path': public_file,
        }
        response = client.post('/api/publish', json=data)

        assert response.status_code == 200
        data = response.json
        assert data['message'] == "File registering. It should be ready soon"
        assert 'file_id' in data

        self.file_id = data['file_id']

        wait = 0
        while wait < 60:
            sleep(2)

            if os.path.exists(published_file):
                break
            wait += 1

        assert os.path.exists(published_file)
        assert os.path.exists(public_file)
        assert not os.path.islink(public_file)
        assert self.md5(published_file) == self.md5(public_file)

    def md5(self, fname):
        hash_md5 = hashlib.md5()
        with open(fname, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
