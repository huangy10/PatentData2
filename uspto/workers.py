# coding=utf-8

# 直接使用ip可以省去极其费时的DNS时间
domain_name = "http://151.207.240.26"

index_url_template = ""


class Task(object):

    def __init__(self, url, task_type, patent, retries=0):
        self.url = url
        self.task_type = task_type
        self.patent = patent
        self.retries = retries

