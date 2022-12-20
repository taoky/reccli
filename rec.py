import base64
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import requests
from Crypto.Cipher import AES
import hashlib


def pad(m: bytes):
    return m + bytes([32 - len(m) % 32]) * (32 - len(m) % 32)


def unpad(m: bytes):
    return m[: -m[-1]]


@dataclass
class UserAuth:
    gid: str
    username: str
    name: str
    auth_token: str
    refresh_token: str


@dataclass
class User:
    number: str
    real_name: str


@dataclass
class FileObject:
    creator: User
    number: str
    name: str
    ext: str
    typ: str
    hash: str
    star: bool
    lock: bool
    mtime: datetime
    size: int


class RecAPI:
    aesKey = base64.b64decode("Z1pNbFZmMmVqd2wwVmlHNA==")
    signatureToken = "VZPDF6HxKyh0hhqFqY2Tk6udzlambRgK"
    apiUrl = "https://recapi.ustc.edu.cn/api/v2/"
    clientID = "d5485a8c-fecb-11e9-b690-005056b70c02"
    user_auth = None
    refreshed = False

    def get(self, path: str, token: bool = True, **kwargs):
        if token:
            if "headers" not in kwargs:
                kwargs["headers"] = {}
            kwargs["headers"]["X-auth-token"] = self.user_auth.auth_token
        response = requests.get(self.apiUrl + path, **kwargs)
        response.encoding = "utf-8-sig"

        try:
            resp = response.json()
        except json.decoder.JSONDecodeError:
            print(response.text)
            raise
        if token and resp["status_code"] == 401:
            self.refresh_token()
            kwargs["headers"]["X-auth-token"] = self.user_auth.auth_token
            response = requests.get(self.apiUrl + path, **kwargs)
            response.encoding = "utf-8-sig"
        return response.json()

    def post(self, path: str, token: bool = True, **kwargs):
        if token:
            if "headers" not in kwargs:
                kwargs["headers"] = {}
            kwargs["headers"]["X-auth-token"] = self.user_auth.auth_token
        response = requests.post(self.apiUrl + path, **kwargs)
        response.encoding = "utf-8-sig"

        try:
            resp = response.json()
        except json.decoder.JSONDecodeError:
            print(response.text)
            raise
        if token and resp["status_code"] == 401:
            self.refresh_token()
            kwargs["headers"]["X-auth-token"] = self.user_auth.auth_token
            response = requests.post(self.apiUrl + path, **kwargs)
            response.encoding = "utf-8-sig"
        return response.json()

    def get_tempticket(self) -> str:
        # client/tempticket verifies clientID,
        # and returns "睿客网进行升级中，请稍后登录。" if the clientID is invalid
        response = self.get(
            "client/tempticket", token=False, params={"clientid": self.clientID}
        )
        if response["status_code"] != 200:
            raise RuntimeError(f"get tempticket failed: {response.get('message')}")
        return response["entity"]["tempticket"]

    def aes_encrypt(self, data):
        cipher = AES.new(self.aesKey, AES.MODE_CBC, iv=self.aesKey[::-1])
        size = len(data)
        payload = int.to_bytes(size, 4, byteorder="big") + data.encode("utf-8")
        # add padding
        payload = pad(payload)
        return base64.b64encode(cipher.encrypt(payload))

    def aes_decrypt(self, data, header_strip=True) -> str:
        cipher = AES.new(self.aesKey, AES.MODE_CBC, iv=self.aesKey[::-1])
        data = base64.b64decode(data)
        raw = cipher.decrypt(data)
        data = unpad(raw)
        if header_strip:
            return data[16:].decode("utf-8")
        else:
            return data.decode("utf-8")

    def serialize_dict(self, dic: dict) -> str:
        return "&".join([key + "=" + dic[key] for key in sorted(dic)])

    def login(self, username, password):
        tempticket = self.get_tempticket()
        login_info = {
            "username": username,
            "password": password,
            "device_type": "PC",
            "client_terminal_type": "client",
            "type": "nusoap",
        }
        string = "A" * 12 + json.dumps(login_info)
        encrypted_str = self.aes_encrypt(string)
        sign = self.signatureToken + self.serialize_dict(
            {"tempticket": tempticket, "msg_encrypt": encrypted_str.decode("utf-8")}
        )
        m = hashlib.md5()
        m.update(sign.encode("utf-8"))
        sign = m.hexdigest().upper()
        response = self.post(
            "user/login?tempticket=" + tempticket + "&sign=" + sign,
            token=False,
            data={"msg_encrypt": encrypted_str.decode("utf-8")},
        )
        if response["status_code"] != 200:
            raise RuntimeError(f"login failed: {response.get('message')}")
        msg_server = response["entity"]["msg_encrypt"]
        msg_server = self.aes_decrypt(msg_server)
        msg_server = json.loads(msg_server)

        auth = UserAuth(
            gid=msg_server["gid"],
            username=msg_server["username"],
            name=msg_server["name"],
            auth_token=msg_server["x_auth_token"],
            refresh_token=msg_server["refresh_token"],
        )
        self.user_auth = auth
        self.refreshed = True

    def refresh_token(self):
        response = self.post(
            "user/refresh/token",
            token=False,
            headers={
                "X-auth-token": self.user_auth.auth_token,
            },
            data={
                "clientid": self.clientID,
                "refresh_token": self.user_auth.refresh_token,
            },
        )
        if response["status_code"] != 200:
            raise RuntimeError(f"refresh token failed: {response.get('message')}")
        msg_server = response["entity"]["msg_encrypt"]
        # why is this different from login?
        msg_server = self.aes_decrypt(msg_server, header_strip=False)
        try:
            msg_server = json.loads(msg_server)
        except json.decoder.JSONDecodeError:
            raise RuntimeError(f"refresh token failed when decoding json: {msg_server}")

        self.user_auth.auth_token = msg_server["x_auth_token"]
        self.user_auth.refresh_token = msg_server["refresh_token"]
        self.refreshed = True
        print("[Token refreshed]")

    def list_by_id(self, id):
        params = {
            "is_rec": "false",
            "category": "all",
            "disk_type": "cloud",
        }
        if id == "B_0":
            params["disk_type"] = "backup"
            id = "0"
        elif id == "R_0":
            params["disk_type"] = "recycle"

        response = self.get(
            f"folder/content/{id}",
            params=params,
        )
        if response["status_code"] != 200:
            raise RuntimeError(f"list_by_id failed: {response.get('message')}")
        objs = []
        for obj in response["entity"]["datas"]:
            objs.append(
                FileObject(
                    creator=User(
                        number=obj["creater_user_number"],
                        real_name=obj["creater_user_real_name"],
                    ),
                    number=obj["number"],
                    name=obj["name"],
                    typ=obj["type"],
                    star=obj["is_star"],
                    lock=obj["is_lock"],
                    mtime=datetime.strptime(
                        obj["last_update_date"], "%Y-%m-%d %H:%M:%S"
                    ),
                    size=int(obj.get("bytes") or 0),
                    ext=obj["file_ext"],
                    hash=obj["hash"],
                )
            )
        return objs

    def download_url_by_id(self, id):
        response = self.post("download", json={"files_list": [id]})
        return response["entity"][id]

    def upload_by_folder_id(self, folder_id: str, file_path: Path):
        filename = file_path.name
        filesize = file_path.stat().st_size
        # 1. Get upload URL
        # TODO: instant upload by calculating file fingerprint first?
        response = self.get(
            "file/" + folder_id,
            params={
                "file_name": filename,
                "byte": filesize,
                "storage": "moss",
                "disk_type": "cloud",
            },
        )
        if response["status_code"] != 200:
            raise RuntimeError(f"upload_by_folder_id failed: {response.get('message')}")
        upload_token = response["entity"]["upload_token"]
        upload_chunk_size = int(response["entity"]["upload_chunk_size"])

        with open(file_path, "rb") as f:
            # 2. Upload file
            for idx, i in enumerate(response["entity"]["upload_params"]):
                data = f.read(upload_chunk_size)
                if not data:
                    break
                upload_url = i[1]["value"]
                upload_method = i[2]["value"]
                if upload_method != "PUT":
                    raise RuntimeError(
                        f"upload_method is not PUT (response = {response})"
                    )

                response = requests.put(
                    upload_url,
                    data=data,
                    headers={
                        "X-auth-token": self.user_auth.auth_token,
                    },
                )

                print(f"Part {idx}: response {response}")

        # 3. Upload complete
        response = self.post(
            "file/complete",
            json={
                "upload_token": upload_token,
            },
        )
        if response["status_code"] != 200:
            raise RuntimeError(f"upload_by_folder_id failed: {response.get('message')}")
        else:
            print("Upload complete")

    def operation_by_id(self, action: str, id, id_type, dst_id=""):
        # only move and copy uses dst_id
        assert action in ["recycle", "delete", "restore", "move", "copy"]
        response = self.post(
            "operationFileOrFolder",
            json={
                "action": action,
                "disk_type": "cloud",
                "files_list": [{"number": id, "type": id_type}],
                "number": "0" if dst_id == "B_0" else dst_id,
            },
        )
        if response["status_code"] != 200:
            raise RuntimeError(f"operation_by_id failed: {response.get('message')}")

    def rename_by_id(self, id, new_name, id_type):
        response = self.post(
            "rename", json={"name": new_name, "number": id, "type": id_type}
        )
        if response["status_code"] != 200:
            raise RuntimeError(f"rename_by_id failed: {response.get('message')}")
    
    def mkdir_by_folder_id(self, folder_id, name):
        response = self.post(
            "folder/tree",
            json={
                "disk_type": "cloud",
                "number": folder_id,
                "paramslist": [name],
            },
        )
        if response["status_code"] != 200:
            raise RuntimeError(f"mkdir_by_folder_id failed: {response.get('message')}")
