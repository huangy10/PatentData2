# coding=utf-8
import os

import requests
import yaml


def read_acount_info():
    base_dir = os.path.dirname(__file__)
    with open(os.path.join(base_dir, "account.yaml"), 'r') as f:
        try:
            data = yaml.load(f)
        except yaml.YAMLError:
            return None, None

        return data["username"], data["password"]


def login(echo_to_file=False, echo_to_screen=False):
    """
    登录到soopat, 返回用于搜索访问的cookies

    :param echo_to_file: 是否将响应的内容写进文件
    :param echo_to_screen:  是否将响应打印到屏幕上
    :return:
    """
    username, password = read_acount_info()
    if username is None or password is None:
        print "Fail to load account info"

    url = "http://adv.soopat.com/Account/Login"
    param = dict(Email=username, Password=password, ReturnUrl="")
    user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) " \
                 "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36"
    res = requests.post(url, param, headers={"user-agent": user_agent}, allow_redirects=False)

    res.raise_for_status()

    if echo_to_file:
        with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "log.html"), "w") as f:
            f.write(res.content)
    if echo_to_screen:
        print res
    return res.cookies


def need_login(res):
    """
    检验一个请求,判断是否需要重新执行登陆
    :param res:
    :return:
    """
    return False
