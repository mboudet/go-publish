import hashlib
import os
import shutil
import tempfile

from gopublish.db_models import PublishedFile
from gopublish.extensions import db


class TestApiView():
    template_repo = "/gopublish/test-data/test-repo/"
    testing_repo = "/repos/myrepo"
    public_file = "/repos/myrepo/my_file_to_publish.txt"
    published_file = "/repos/myrepo/public/my_file_to_publish_v1.txt"
    file_id = ""

    def setup_method(self):
        if os.path.exists(self.testing_repo):
            shutil.rmtree(self.testing_repo)
        shutil.copytree(self.template_repo, self.testing_repo)

    def teardown_method(self):
        if os.path.exists(self.testing_repo):
            shutil.rmtree(self.testing_repo)
        if self.file_id:
            for file in PublishedFile.query.filter(PublishedFile.id == self.file_id):
                db.session.delete(file)
            db.session.commit()
            self.file_id = ""

    def test_view_incorrect_id(self, client):
        """
        Get file with incorrect id
        """

        fake_id = "XXX"
        url = "/api/view/" + fake_id
        response = client.get(url)

        assert response.status_code == 404
        assert response.json == {}

    def test_view_missing_file(self, client):
        """
        Get file with correct id, but file not created
        """

        fake_id = "f2ecc13f-3038-4f78-8c84-ab881a0b567d"
        url = "/api/view/" + fake_id
        response = client.get(url)

        assert response.status_code == 404
        assert response.json == {}

    def test_view_existing_file(self, client):
        self.file_id = self.create_mock_published_file(client, "available")
        size = os.path.getsize(self.published_file)
        hash = self.md5(self.published_file)

        url = "/api/view/" + self.file_id
        response = client.get(url)

        assert response.status_code == 200
        data = response.json['file']
        data.pop('publishing_date', None)

        assert data == {
            "contact": None,
            "owner": "root",
            "status": "available",
            "file_name": "my_file_to_publish.txt",
            "version": 1,
            "size": size,
            "hash": hash,
        }

    def test_download_existing_file(self, client):
        self.file_id = self.create_mock_published_file(client, "available")

        url = "/api/download/" + self.file_id
        response = client.get(url)

        assert response.status_code == 200

        with tempfile.TemporaryDirectory() as local_path:
            local_file = local_path + '/myfile'
            with open(local_file, "wb") as f:
                f.write(response.data)

            assert self.md5(local_file) == self.md5(self.published_file)

    def test_search(self, client):
        self.file_id = self.create_mock_published_file(client, "available")
        size = os.path.getsize(self.published_file)

        url = "/api/search?file=my_file_to_publish"
        response = client.get(url)

        assert response.status_code == 200

        data = response.json['data']

        assert len(data) == 1
        assert data[0] == {
            'uri': self.file_id,
            'file_name': "my_file_to_publish.txt",
            'size': size,
            'version': 1,
            'downloads': 0,
            'status': "available"
        }

    def create_mock_published_file(self, client, status):
        file_name = "my_file_to_publish.txt"
        public_file = self.public_file
        published_file = self.published_file
        size = os.path.getsize(public_file)
        hash = self.md5(public_file)
        # Copy file in public repo
        shutil.copy(public_file, published_file)
        size = os.path.getsize(public_file)
        pf = PublishedFile(file_name=file_name, stored_file_name="my_file_to_publish_v1.txt", repo_path="/repos/myrepo", version=1, size=size, hash=hash, status=status, owner="root")
        db.session.add(pf)
        db.session.commit()
        return str(pf.id)

    def md5(self, fname):
        hash_md5 = hashlib.md5()
        with open(fname, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
