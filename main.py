import dataclasses
import json
from pathlib import Path
import subprocess
import traceback
import keyring
from rec import RecAPI, UserAuth
import rec   # typing
from getpass import getpass
from urllib.parse import urlparse, parse_qs
import readline
from tabulate import tabulate
from urllib.parse import unquote
import shlex

readline.parse_and_bind("tab: complete")

api = RecAPI()
service_name = "reccli"


def login() -> None:
    print(
        "By default, your CAS username and password will be sent to https://recapi.ustc.edu.cn"
    )
    print(
        "You can login in browser manually and paste the output of `document.cookie` in Developer Console instead"
    )
    username = input("Username or cookie: ")
    if "Rec-Token" in username:
        # strip out whitespace
        username = username.strip()
        # parse username as cookie
        cookie = dict(i.split("=", 1) for i in username.strip('"').split("; "))

        auth_token = cookie["Rec-Token"]
        refresh_otken = json.loads(unquote(cookie["Rec-RefreshToken"]))["refresh_token"]
        user_auth = UserAuth(
            gid="Unknown",
            username="Unknown",
            name="Unknown",
            auth_token=auth_token,
            refresh_token=refresh_otken,
        )
        api.user_auth = user_auth
        api.refreshed = True
    else:
        password = getpass("Password: ")
        api.login(username, password)


def update_keyring() -> None:
    assert api.user_auth is not None
    keyring.set_password(
        service_name, "userauth", json.dumps(dataclasses.asdict(api.user_auth))
    )


def auth() -> None:
    userauth_json = keyring.get_password(service_name, "userauth")
    if userauth_json is None:
        login()
        update_keyring()
    else:
        user_auth = UserAuth(**json.loads(userauth_json))
        api.user_auth = user_auth


def obj_name(obj: rec.FileObject) -> str:
    if obj.ext:
        return f"{obj.name}.{obj.ext}"
    else:
        return obj.name


def get_final_id(id: str) -> str:
    return id.rsplit("/", maxsplit=1)[-1]


def crawl(path: str, cwd_path: str, cwd_id: str) -> tuple[str, str]:
    if path.startswith("/"):
        cwd_path = "/"
        cwd_id = "0"
        path = path[1:]
    path_components = path.split("/")
    for idx, component in enumerate(path_components):
        if cwd_path == "/" and component == "?Backup":
            cwd_path = "/?Backup/"
            cwd_id = "0/B_0"
        elif cwd_path == "/" and component == "?Recycle":
            cwd_path = "/?Recycle/"
            cwd_id = "0/R_0"
        elif component == "" or component == ".":
            continue
        elif component == "..":
            if cwd_path == "/":
                continue
            cwd_path = "/".join(cwd_path.split("/")[:-2]) + "/"
            cwd_id = cwd_id.rsplit("/", maxsplit=1)[0]
        else:
            objs = api.list_by_id(get_final_id(cwd_id))
            found = False
            for obj in objs:
                name = obj_name(obj)
                obj_type = obj.typ
                if name == component:
                    found = True
                    if obj_type == "folder":
                        cwd_path = f"{cwd_path}{name}/"
                        cwd_id += "/" + obj.number
                        break
                    elif obj_type == "file":
                        cwd_path = f"{cwd_path}{name}"
                        cwd_id += "/" + obj.number
                        if idx != len(path_components) - 1:
                            raise RuntimeError("Not a folder")
            if not found:
                raise RuntimeError("Not found")
    return cwd_path, cwd_id


# https://stackoverflow.com/a/1094933
def sizeof_fmt(num: int | float, suffix : str = "B") -> str:
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f} {unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f} Yi{suffix}"


def check_id_type(id_type: str) -> None:
    if id_type != "file" and id_type != "folder":
        raise ValueError("Invalid type: should be file or folder")


def main() -> None:
    cwd_path = "/"
    cwd_id = "0"

    while True:
        if api.refreshed:
            update_keyring()
            api.refreshed = False
        try:
            user_input = input(f"[{cwd_path}] > ").strip()
        except EOFError:
            exit(0)
        except KeyboardInterrupt:
            print("")
            continue
        splitted = shlex.split(user_input)
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
                print(cwd_path, cwd_id)
                print("Userinfo:", api.userinfo())
            elif command == "help":
                print("Available commands:")
                print("exit, login, refresh, info, help")
                print("ls, cd, get, put, rm")
                print("rename, copy, move, restore, mkdir")
                print("df")
                print("Debugging commands:")
                print(
                    "list_id, download_id, upload_to_folder_id, recycle_id, restore_id, rename_id"
                )
                print("delete_id, copy_id, move_id, mkdir_id, rename_id_ext")
            elif command == "list_id":
                if len(splitted) != 2:
                    print("Usage: list_id <id>")
                    continue
                lid = splitted[1]
                objs = api.list_by_id(lid)
                for obj in objs:
                    print(obj)
            elif command == "download_id":
                if len(splitted) not in (2, 3):
                    print("Usage: download_id <id> [<dest>]")
                    continue
                did = splitted[1]
                if len(splitted) == 3:
                    dest = splitted[2]
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
                if len(splitted) != 3:
                    print("Usage: upload_to_folder_id <folder_id> <local_file>")
                    continue

                fid = splitted[1]
                local_file = Path(splitted[2])

                api.upload_by_folder_id(fid, local_file)
            elif command == "recycle_id" or command == "delete_id":
                if len(splitted) not in (2, 3):
                    print(f"Usage: {command} <id> [<type (default=file)>]")
                    continue
                rid = splitted[1]
                if len(splitted) == 3:
                    id_type = splitted[2]
                    check_id_type(id_type)
                else:
                    id_type = "file"
                if command == "delete_id":
                    y = input("Deleting is irreversible. Are you sure? (y/N) ")
                    if y != "y":
                        print("Aborted.")
                        continue
                action = "recycle" if command == "recycle_id" else "delete"
                api.operation_by_id(action, rid, id_type)
            elif command == "rename_id" or command == "rename_id_ext":
                if len(splitted) not in (3, 4):
                    print(f"Usage: {command} <id> <new_name> [<type (default=file)>]")
                    continue
                rid = splitted[1]
                new_name = splitted[2]
                if len(splitted) == 4:
                    id_type = splitted[3]
                    check_id_type(id_type)
                else:
                    id_type = "file"
                if command == "rename_id":
                    api.rename_by_id(rid, new_name, id_type)
                else:
                    if id_type != "file":
                        raise ValueError("rename_id_ext only works on files")
                    api.rename_by_id_ext(rid, new_name)
            elif (
                command == "copy_id" or command == "move_id" or command == "restore_id"
            ):
                if len(splitted) not in (3, 4):
                    print(f"Usage: {command} <dst_id> <src_id> [<type (default=file)>]")
                    continue
                dst_id = splitted[1]
                src_id = splitted[2]
                if len(splitted) == 4:
                    id_type = splitted[3]
                    check_id_type(id_type)
                else:
                    id_type = "file"
                if command == "copy_id":
                    action = "copy"
                elif command == "move_id":
                    action = "move"
                elif command == "restore_id":
                    action = "restore"
                else:
                    assert 0
                api.operation_by_id(action, src_id, id_type, dst_id)
            elif command == "mkdir_id":
                if len(splitted) != 3:
                    print("Usage: mkdir_id <parent_id> <name>")
                    continue
                pid = splitted[1]
                name = splitted[2]
                api.mkdir_by_folder_id(pid, name)
            elif command == "ls":
                if len(splitted) == 1:
                    did = get_final_id(cwd_id)
                elif len(splitted) == 2:
                    path, id = crawl(splitted[1], cwd_path, cwd_id)
                    if path[-1] != "/":
                        raise ValueError(
                            "ls does not support showing single file stats"
                        )
                    did = id
                else:
                    print("Usage: ls [<path>]")
                    continue
                objs = api.list_by_id(did)
                table = []
                if did == "0":
                    table.append(["[?Backup/]", "System", "", ""])
                    table.append(["[?Recycle/]", "System", "", ""])
                for obj in objs:
                    name = obj_name(obj)
                    if obj.typ == "folder":
                        name = f"[{name}/]"
                    table.append([name, obj.creator.real_name, str(obj.size), str(obj.mtime)])
                print(tabulate(table, headers=["Name", "Creator", "Size", "Modified"]))
            elif command == "cd":
                if len(splitted) != 2:
                    print("Usage: cd <path>")
                    continue
                cwd_path, cwd_id = crawl(splitted[1], cwd_path, cwd_id)
            elif command == "get":
                if len(splitted) != 2:
                    print("Usage: get <path>")
                    continue
                path, id = crawl(splitted[1], cwd_path, cwd_id)
                id = get_final_id(id)
                if path[-1] == "/":
                    print("Cannot get directory")
                    continue
                print(f"Getting {path} ({id})")
                url = api.download_url_by_id(id)
                print(f"You can download this file via: {url}")
            elif command == "put":
                if len(splitted) != 2:
                    print("Usage: put <local_file>")
                    continue
                local_file = Path(splitted[1])

                print(f"Uploading {local_file} to current working directory")
                api.upload_by_folder_id(get_final_id(cwd_id), local_file)
            elif command == "rm":
                if len(splitted) != 2:
                    print("Usage: rm <path>")
                    continue
                path, id = crawl(splitted[1], cwd_path, cwd_id)
                filetype = "folder" if path[-1] == "/" else "file"
                if "?Recycle" in path:
                    y = input(
                        f"Are you sure to permanently delete this {filetype}? (y/N) "
                    )
                    if y != "y":
                        print("Aborted.")
                        continue
                    action = "delete"
                else:
                    action = "recycle"
                api.operation_by_id(action, get_final_id(id), filetype)
            elif command == "rename":
                if len(splitted) != 3:
                    print("Usage: rename <path> <new_name>")
                    continue
                path, id = crawl(splitted[1], cwd_path, cwd_id)
                filetype = "folder" if path[-1] == "/" else "file"
                new_name = splitted[2]
                if filetype == "file":
                    # rename_by_id does not support file ext renaming
                    # see https://github.com/taoky/reccli/issues/1 for more information
                    api.rename_by_id_ext(get_final_id(id), new_name)
                else:
                    api.rename_by_id(get_final_id(id), new_name, filetype)
            elif command == "copy" or command == "move" or command == "restore":
                if len(splitted) != 3:
                    print(f"Usage: {command} <src> <dst_dir>")
                    continue
                path, id = crawl(splitted[1], cwd_path, cwd_id)
                dst_path, dst_id = crawl(splitted[2], cwd_path, cwd_id)
                filetype = "folder" if path[-1] == "/" else "file"
                if dst_path[-1] != "/":
                    raise ValueError("Destination should be a directory")
                if command == "restore" and "?Recycle" not in path:
                    raise ValueError("restore only works on files in recycle bin")
                api.operation_by_id(
                    command, get_final_id(id), filetype, get_final_id(dst_id)
                )
            elif command == "mkdir":
                if len(splitted) != 2:
                    print("Usage: mkdir <name>")
                    continue
                api.mkdir_by_folder_id(get_final_id(cwd_id), splitted[1])
            elif command == "df":
                userinfo = api.userinfo()
                used = int(userinfo["used_space"])
                total = int(userinfo["total_space"])
                print(
                    f"User disk usage: {used} B / {total} B ({sizeof_fmt(used)} / {sizeof_fmt(total)})"
                )
            else:
                print(f"Unknown command: {command}")

        except Exception:
            print(f"Error occurred when executing {command}:")
            traceback.print_exc()


if __name__ == "__main__":
    auth()
    main()
