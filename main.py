import dataclasses
import json
from pathlib import Path
import subprocess
import traceback
import keyring
from rec import RecAPI, UserAuth
from getpass import getpass
from urllib.parse import urlparse, parse_qs
import readline

readline.parse_and_bind("tab: complete")

api = RecAPI()
service_name = "reccli"


def login():
    username = input("Username: ")
    password = getpass("Password: ")
    api.login(username, password)


def update_keyring():
    keyring.set_password(
        service_name, "userauth", json.dumps(dataclasses.asdict(api.user_auth))
    )


def auth():
    userauth_json = keyring.get_password(service_name, "userauth")
    if userauth_json is None:
        username = input("Username: ")
        password = getpass("Password: ")
        api.login(username, password)
        update_keyring()
    else:
        user_auth = UserAuth(**json.loads(userauth_json))
        api.user_auth = user_auth


def main():
    while True:
        if api.refreshed:
            update_keyring()
            api.refreshed = False
        try:
            user_input = input("> ").strip()
        except EOFError:
            exit(0)
        except KeyboardInterrupt:
            print("")
            continue
        splitted = user_input.split(None, maxsplit=1)
        if len(splitted) == 0:
            continue
        command = splitted[0]
        try:
            if command == "exit":
                exit(0)
            elif command == "login":
                login()
            elif command == "refresh":
                api.refresh_token()
            elif command == "info":
                print(api.user_auth)
            elif command == "help":
                print("Available commands:")
                print("exit, login, refresh, info, help")
                print("Debugging commands:")
                print(
                    "list_id, download_id, upload_to_folder_id, recycle_id, restore_id, rename_id"
                )
                print("delete_id, copy_id, move_id")
            elif command == "list_id":
                if len(splitted) == 1:
                    print("Usage: list_id <id>")
                    continue
                lid = splitted[1]
                objs = api.list_by_id(lid)
                for obj in objs:
                    print(obj)
            elif command == "download_id":
                if len(splitted) == 1:
                    print("Usage: download_id <id> [<dest>]")
                    continue
                sub_splitted = splitted[1].split(maxsplit=1)
                did = sub_splitted[0]
                if len(sub_splitted) > 1:
                    dest = sub_splitted[1]
                else:
                    dest = "./"
                url = api.download_url_by_id(did)
                print(url)
                url_components = urlparse(url)
                filename = parse_qs(url_components.query)["filename"][0]
                print("Calling curl...")
                try:
                    if Path(dest).is_dir():
                        print(
                            f"Downloading to directory {dest} with filename {filename}"
                        )
                        subprocess.run(["curl", "-L", url, "-o", filename], cwd=dest)
                    else:
                        print(f"Downloading to file {dest}")
                        subprocess.run(["curl", "-L", url, "-o", dest])
                except KeyboardInterrupt:
                    print("(Interrupted)")
            elif command == "upload_to_folder_id":
                if len(splitted) == 1:
                    sub_splitted = None
                else:
                    sub_splitted = splitted[1].split(maxsplit=1)
                if len(splitted) == 1 or len(sub_splitted) != 2:
                    print("Usage: upload_to_folder_id <folder_id> <local_file>")
                    continue

                fid = sub_splitted[0]
                local_file = Path(sub_splitted[1])

                api.upload_by_folder_id(fid, local_file)
            elif command == "recycle_id":
                if len(splitted) == 1:
                    print("Usage: recycle_id <id> [<type (default=file)>]")
                    continue
                sub_splitted = splitted[1].split(maxsplit=1)
                rid = sub_splitted[0]
                if len(sub_splitted) > 1:
                    id_type = sub_splitted[1]
                    if id_type != "file" and id_type != "folder":
                        raise ValueError("Invalid type: should be file or folder")
                else:
                    id_type = "file"
                api.operation_by_id("recycle", rid, id_type)
            elif command == "restore_id":
                if len(splitted) == 1:
                    print("Usage: restore_id <dst_id> <id> [<type (default=file)>]")
                    continue
                sub_splitted = splitted[1].split(maxsplit=2)
                dst_id = sub_splitted[0]
                rid = sub_splitted[1]
                if len(sub_splitted) > 2:
                    id_type = sub_splitted[2]
                    if id_type != "file" and id_type != "folder":
                        raise ValueError("Invalid type: should be file or folder")
                else:
                    id_type = "file"
                api.operation_by_id("restore", rid, id_type, dst_id)
            elif command == "delete_id":
                if len(splitted) == 1:
                    print("Usage: delete_id <id> [<type (default=file)>]")
                    continue
                sub_splitted = splitted[1].split(maxsplit=1)
                rid = sub_splitted[0]
                if len(sub_splitted) > 1:
                    id_type = sub_splitted[1]
                    if id_type != "file" and id_type != "folder":
                        raise ValueError("Invalid type: should be file or folder")
                else:
                    id_type = "file"
                y = input("Deleting is irreversible. Are you sure? (y/N) ")
                if y != "y":
                    print("Aborted.")
                    continue
                api.operation_by_id("delete", rid, id_type)
            elif command == "rename_id":
                if len(splitted) == 1:
                    print("Usage: rename_id <id> <new_name> [<type (default=file)>]")
                    continue
                sub_splitted = splitted[1].split(maxsplit=2)
                rid = sub_splitted[0]
                new_name = sub_splitted[1]
                if len(sub_splitted) > 2:
                    id_type = sub_splitted[2]
                    if id_type != "file" and id_type != "folder":
                        raise ValueError("Invalid type: should be file or folder")
                else:
                    id_type = "file"
                api.rename_by_id(rid, new_name, id_type)
            elif command == "copy_id":
                if len(splitted) == 1:
                    print("Usage: copy_id <dst_id> <src_id> [<type (default=file)>]")
                    continue
                sub_splitted = splitted[1].split(maxsplit=2)
                dst_id = sub_splitted[0]
                src_id = sub_splitted[1]
                if len(sub_splitted) > 2:
                    id_type = sub_splitted[2]
                    if id_type != "file" and id_type != "folder":
                        raise ValueError("Invalid type: should be file or folder")
                else:
                    id_type = "file"
                api.operation_by_id("copy", src_id, id_type, dst_id)
            elif command == "move_id":
                if len(splitted) == 1:
                    print("Usage: move_id <dst_id> <src_id> [<type (default=file)>]")
                    continue
                sub_splitted = splitted[1].split(maxsplit=2)
                dst_id = sub_splitted[0]
                src_id = sub_splitted[1]
                if len(sub_splitted) > 2:
                    id_type = sub_splitted[2]
                    if id_type != "file" and id_type != "folder":
                        raise ValueError("Invalid type: should be file or folder")
                else:
                    id_type = "file"
                api.operation_by_id("move", src_id, id_type, dst_id)

        except Exception:
            print(f"Error occurred when executing {command}:")
            traceback.print_exc()


if __name__ == "__main__":
    auth()
    main()
