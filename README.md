# reccli

A proof-of-concept of rec.ustc.edu.cn client.

Note that now it uses some new type-hint features of Python, thus requiring Python 3.10+.

## Example

```console
> python main.py
[/] > ls
Name                                              Creator    Size        Modified
------------------------------------------------  ---------  ----------  -------------------
[?Backup/]                                        System
[?Recycle/]                                       System
[crypto/]                                         User       0           2022-12-19 22:02:33
vmware-vmvisor.iso                                User       375341056   2022-12-20 00:30:29
[/] > get vmware-vmvisor.iso
Getting /vmware-vmvisor.iso (0e916820-68b2-11ea-95eb-15c114681ad7)
You can download this file via: https://recstore.ustc.edu.cn/file/<redacted>?Signature=<redacted>=&Expires=1671555378&AccessKeyId=<redacted>&response-content-type=application%2Foctet-stream&response-content-disposition=attachment%3Bfilename%3D%22vmware-vmvisor.iso%22&storage=moss&filename=vmware-vmvisor.iso
[/] > mkdir example
[/] > cd example
[/example/] > ls
Name    Creator    Size    Modified
------  ---------  ------  ----------
[/example/] > put /etc/os-release
Uploading /etc/os-release to current working directory
Part 0: response <Response [200]>
Upload complete
[/example/] > ls
Name        Creator      Size  Modified
----------  ---------  ------  -------------------
os-release  User          355  2022-12-20 00:57:38
[/example/] > rename os-release testfile
[/example/] > ls
Name      Creator      Size  Modified
--------  ---------  ------  -------------------
testfile  User          355  2022-12-20 00:58:14
[/example/] > rm testfile
[/example/] > cd /?Recycle
[/?Recycle/] > ls
Name         Creator         Size  Modified
-----------  ---------  ---------  -------------------
testfile     User             355  2022-12-20 00:58:33
os-release   User             355  2022-12-20 00:49:20
[新建文件夹(1)/]  User               0  2022-12-20 00:46:09
[新建文件夹/]     User               0  2022-12-20 00:45:58
crypto.7z    User       438740493  2022-01-21 18:37:18
[/?Recycle/] > rm 新建文件夹
Are you sure to permanently delete this folder? (y/N) y
[/?Recycle/] > ls
Name         Creator         Size  Modified
-----------  ---------  ---------  -------------------
testfile     User             355  2022-12-20 00:58:33
os-release   User             355  2022-12-20 00:49:20
[新建文件夹(1)/]  User               0  2022-12-20 00:46:09
crypto.7z    User       438740493  2022-01-21 18:37:18
[/?Recycle/] > cd /example/
[/example/] > copy /vmware-vmvisor.iso .
[/example/] > ls
Name                Creator         Size  Modified
------------------  ---------  ---------  -------------------
vmware-vmvisor.iso  User       375341056  2022-12-20 01:01:01
```
