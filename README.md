# 关于PatentData2 #github#
## 介绍
2016.12.19 Updates:
取消了原来master中的全面查询十四年内所有专利数据的版本，将原single_year分支的单年份爬取功能合并到master了。

这个工程是基于 [PatentData](https://github.com/huangy10)的改进版。其作用是爬取并分析来自专利相关搜索引擎的专利数据，并分析这些数据之间的关联。目前这个工程主要涉及了[soopat](www.soopat.com)以及 [USPTO](https://www.uspto.gov)这两个搜索引擎。然而，由于soopat这个网站限制了每个账户每天最多能够获取的专利数量的限制（大约在每天3000条），故实际上工程主要面向的还是USPTO这个搜索引擎，即主要是`uspto`和`uspto_fast`两个包内的内容。

### `uspto`
`uspto`下的程序主要是按照逐个国家检索其在2001年至2014年之间在uspto注册的所有专利，目前这些国家的种类是固定的，如果需要配置的话，可以修改`Patent/data/country_code.xlsx`内的内容来指定。

爬取的结果存储在`uspto/db.sqlite3`中。我们选择了**SQLAlchemy**来作为ORM，你可以通过`Patent/models.py`中的内容来操作和读取数据。

### `uspto_fast`
之所有创建了一个**fast**的版本，是因为uspto引擎在搜索属于美国的专利的时候，其速度回非常缓慢（需要数十秒的时间才能返回结果），因此我们创建了一个快速版本，不按国籍归属，而是全面查询2001年到2014年的所有国家的专利（预估有超过三百万条）。在`single_year`分支中，还提供了单独查询某一年份的专利的版本，方便里分布在多台机器上同时爬取。

### How to Use
上述的两个模块都是通过运行其下的`runme.py`来执行。这个python脚本可以接受额外的命令行参数。

`uspto`可以接受两个额外的参数，第一个指定的是创建的搜索爬虫数量（目前来看一般不超过2个，因为每个搜索爬虫还下还有若干子爬虫在运行），第二个参数指的是跳过的页数。

`uspto_fast`在master分支下的版本只能接受一个参数，即搜索爬虫的数量，在single_year分支下还可以额外接受一个参数，该参数用来确定想要爬取的年份。

## 原理
这个工程核心机制有两个部分，一是通过tornado构建的基于协程的异步IO的爬虫系统，另一个是基于SQLAlchemy的Model部分。