# -*- encoding: utf-8 -*-
import json
import logging
import sys
import time

from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, render_to_response

from crawlermanage.models import Task, News, Process, Machine, User, Goods, Stores, Blog, TempArticle
from crawlermanage.utils.article_parser import extract, test, readFile, extract_content, get_article_data
from crawlermanage.utils.echarts import create_chart1, create_chart2, create_chart3, create_chart4
from crawlermanage.utils.ecommerce.pageParser.shopping_detail_parser  import get_goods_dict
from crawlermanage.utils.ecommerce.pageParser.shopping_navigation_parser  import get_nav
from crawlermanage.utils.ecommerce.pageParser.shopping_itemsList_parser  import get_goods_list
from crawlermanage.utils.ecommerce.spiderUtils.parser_util import get_soup_by_request
from crawlermanage.utils.message import Message
from crawlermanage.utils.page import paging
from crawlermanage.utils.settings_helper import get_attr

reload(sys)
sys.setdefaultencoding('utf-8')

logger = logging.getLogger('crawlermanage.views')
# mongoengine.register_connection('default', 'p')

# Create your views here.
redis_host = get_attr('REDIS_HOST')
sub = get_attr('SUBSCRIBE')
messager = Message(redis_host)
messager.subscribe(sub)

'''
    登录
'''


def login(request):
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = User.objects.filter(username=username, password=password)
        if (username == 'admin' and password == 'a') or (len(user) != 0):
            return HttpResponseRedirect('/crawlermanage/index')
        else:
            return render_to_response('crawlermanage/login.html', {'error': '用户名或密码错误'})
    else:
        return render_to_response('crawlermanage/login.html')


def index(request):
    return render(request, 'crawlermanage/index.html')


'''
    爬虫任务列表
    p:正在进行、等待运行、出现故障的任务
    p2:结束的任务
'''


def tasks(request):
    page = request.GET.get('page')
    page2 = request.GET.get('page2')
    webpage = 'currenttask'
    if page == None:
        page = 1
    else:
        webpage = 'currenttask'
    if page2 == None:
        page2 = 1
    else:
        webpage = 'historytask'

    list = Task.objects.filter(status__in=['running', 'waitting', 'error', 'pausing'])
    list2 = Task.objects.filter(status='stopping')

    p = paging(list, page, 10)
    p2 = paging(list2, page2, 10)

    running_count = Task.objects.filter(status='running').count()
    pausing_count = Task.objects.filter(status='pausing').count()
    stopping_count = Task.objects.filter(status='stopping').count()
    error_count = Task.objects.filter(status='error').count()

    return render(request, 'crawlermanage/tasks.html', {'p': p, 'p2': p2, 'status':webpage,'running_count': running_count,
                                                        'pausing_count': pausing_count,
                                                        'stopping_count': stopping_count, 'error_count': error_count})


'''
    编辑爬虫状态：暂停/唤醒/结束
'''


def edittask(request):
    if request.method == 'POST':
        op = request.POST.get('op')
        taskid = request.POST.get('taskid')
        task = Task.objects.filter(id=taskid)
        logger.info(task)
        if op == 'running':
            task.update(status='running')
            msg = 'op=resumetask&taskid=' + taskid
            messager.publish('crawler', msg)
            ret = {'status': 'success', 'taskstatus': 'running'}
            return HttpResponse(json.dumps(ret))
        elif op == 'pausing':
            task.update(status='pausing')
            msg = 'op=suspendtask&taskid=' + taskid
            messager.publish('crawler', msg)
            ret = {'status': 'success', 'taskstatus': 'pausing'}
            return HttpResponse(json.dumps(ret))
        elif op == 'stopping':
            task.update(status='stopping')
            msg = 'op=terminatetask&taskid=' + taskid
            messager.publish('crawler', msg)
            ret = {'status': 'success', 'taskstatus': 'stopping'}
            return HttpResponse(json.dumps(ret))


def editprocess(request):
    if request.method == 'POST':
        op = request.POST.get('op')
        processid = request.POST.get('processid')
        # process = Process.objects.filter(id=processid)
        logger.info(processid)
        if op == 'running':
            msg = 'op=resumeprocess&processid=' + processid
            messager.publish('crawler', msg)
            ret = {'status': 'success', 'process_status': 'running'}
            return HttpResponse(json.dumps(ret))
        elif op == 'pausing':
            msg = 'op=suspendprocess&processid=' + processid
            messager.publish('crawler', msg)
            ret = {'status': 'success', 'process_status': 'pausing'}
            return HttpResponse(json.dumps(ret))
        elif op == 'stopping':
            msg = 'op=terminateprocess&processid=' + processid
            messager.publish('crawler', msg)
            ret = {'status': 'success', 'process_status': 'stopping'}
            return HttpResponse(json.dumps(ret))


def ecommercedata(request):
    return render(request, 'crawlermanage/ecommercedata.html')


# def newsdata(request):
#     # newslist = News.objects.all()
#     # return render(request, 'crawlermanage/newsdata.html', {'newslist':newslist})
#     limit = 10  # 每页显示的记录数
#     allnews = News.objects.all()
#     logger.info("allnews:")
#     logger.info(len(allnews))
#     paginator = Paginator(allnews, limit)  # 实例化一个分页对象
#
#     page = request.GET.get('page')  # 获取页码
#     try:
#         newslist = paginator.page(page)  # 获取某页对应的记录
#     except PageNotAnInteger:  # 如果页码不是个整数
#         newslist = paginator.page(1)  # 取第一页的记录
#     except EmptyPage:  # 如果页码太大，没有相应的记录
#         newslist = paginator.page(paginator.num_pages)  # 取最后一页的记录
#     logger.info("newslist:")
#     logger.info(len(newslist))
#     return render(request, 'crawlermanage/newsdata.html', {'newslist': newslist})

'''
    新闻列表
'''


def newsdata(request):
    taskid = request.GET.get('taskid')
    list = []
    if taskid != None:
        list = News.objects.filter(taskid=taskid)
    page = request.GET.get('page')
    if page == None:
        page = 1
    p = paging(list, page, 10)
    return render(request, 'crawlermanage/newsdata.html', locals())


'''
    新闻详细内容
'''


def newsdetail(request):
    id = request.GET.get('id')
    if id == None:
        return
    news = News.objects.get(id=id)
    if news == None:
        return
    return render(request, 'crawlermanage/newsdetail.html', {'news': news})


'''
    布置爬虫任务
'''


def layout(request):
    ips = Machine.objects.all()
    if request.method == 'POST':
        taskname = request.POST.get('taskname', '')
        starturls = request.POST.get('starturls', '')
        describe = request.POST.get('describe', '')
        webtype = request.POST.get('webtype', '')
        reservationtime = request.POST.get('reservationtime', '')
        slave = request.POST.get('slave', '')
        processnum = request.POST.get('processnum', '')
        keywords = request.POST.get('keywords', '')
        keyword_list = []
        if keywords!='':
            keyword_list = keywords.split(',')
        logger.info(keywords)
        if processnum == '':
            processnum = 1
        processnum = int(processnum)
        list_url = starturls.split('\n')
        starttime = ''
        endtime = ''
        if reservationtime == '':
            starttime = time.strftime("%Y/%m/%d %H:%M")
            status = 'running'
        else:
            temp = reservationtime.split('-')
            starttime = temp[0].strip()
            endtime = temp[1].strip()
            status = 'waitting'
        slave_list = []
        if slave == '':
            slave = get_attr('LOCAL_HOST')
        slave_list = slave.split(',')
        if webtype =='ecommerce_keywords':
            webtype = 'ecommerce'
        task = Task.objects.create(taskname=taskname, starturls=list_url, starttime=starttime, endtime=endtime,
                                   webtype=webtype, describe=describe, slave=slave_list, status=status,
                                   processnum=processnum, keywords=keyword_list)
        taskid = str(task['id'])
        logger.info(status)
        msg = 'op=starttask&taskid=' + taskid  # + "&status=" + status
        messager.publish('crawler', msg)
        ret = {'status': 'success'}
        return HttpResponse(json.dumps(ret))
    else:
        return render_to_response('crawlermanage/layout.html', {'ips': ips})


'''
    爬虫任务详情
'''


def taskdetail(request):
    taskid = request.GET.get('taskid')
    logger.info(taskid)

    task = Task.objects.get(id=taskid)
    logger.info(task.status)
    return render_to_response('crawlermanage/taskdetail.html', {'task': task})


'''
    测试正文
'''


def extractarticle(request):
    if request.method == 'POST':
        original_folder = request.POST.get('original_folder', '')
        goal_folder = request.POST.get('goal_folder', '')
        extract(original_folder, goal_folder)
        ret = {'isFinished': 'yes'}
        return HttpResponse(json.dumps(ret))
    else:
        return render_to_response('crawlermanage/extract_article.html')


'''多文件测试'''


def testarticles(request):
    if request.method == 'POST':
        original_folder = request.POST.get('original_folder', '')
        goal_folder = request.POST.get('goal_folder', '')
        try:
            log, score = test(original_folder, goal_folder)
            ret = {'log': log, 'score': score}
        except:
            ret = {'error': 'error'}
        return HttpResponse(json.dumps(ret))
    else:
        return render_to_response('crawlermanage/test_articles.html')


'''
    测试结果
'''


def testlist(request):
    return render_to_response('crawlermanage/test_list.html')


def processlist(request):
    page = request.GET.get('page')
    if page == None:
        page = 1
    list = Process.objects.filter(status__in=['running', 'pausing'])
    p = paging(list, page, 10)
    tasknames = []
    for i in p.p_content:
        logger.info(i.taskid)
        name = Task.objects.get(id=i.taskid)['taskname']
        tasknames.append(name)
    pc_name = zip(p.p_content, tasknames)
    return render(request, 'crawlermanage/process_list.html', {'p': p, 'pc_name': pc_name})


def machinelist(request):
    page = request.GET.get('page')
    if page == None:
        page = 1
    list = Machine.objects.all()
    p = paging(list, page, 10)
    return render(request, 'crawlermanage/machine_list.html', {'p': p})


'''删除ip'''


def deleteip(request):
    ip = request.GET.get('ip')
    if ip != None:
        Machine.objects.filter(ip=ip).delete()
    return HttpResponseRedirect('/crawlermanage/machinelist')


'''增加ip'''


def addip(request):
    if request.method == 'POST':
        ip = request.POST.get('ip', '').strip()
        machine = Machine.objects.filter(ip=ip)
        if len(machine) == 0:
            machine = Machine(ip=ip)
            machine.save()
            ret = {"status": "success"}
        else:
            ret = {"status": "error"}
        return HttpResponse(json.dumps(ret))
    else:
        ret = {"status": "error"}
        return HttpResponse(json.dumps(ret))


'''数据统计——报表'''


def charts(request):
    chart1_run, chart1_pause, chart1_wait, chart1_error = create_chart1()
    chart1 = {'run': chart1_run, 'pause': chart1_pause, 'wait': chart1_wait, 'error': chart1_error}
    chart2_ecommerce, chart2_news, chart2_blog = create_chart2()
    chart2 = {'ecommerce': chart2_ecommerce, 'news': chart2_news, 'blog': chart2_blog}
    chart3_ecommerce, chart3_news, chart3_blog = create_chart3()
    chart3 = {'ecommerce': chart3_ecommerce, 'news': chart3_news, 'blog': chart3_blog}
    chart4_ip, chart4_num = create_chart4()
    chart4 = {'ips': chart4_ip, 'processnum': chart4_num}
    return render(request, 'crawlermanage/charts.html', {'chart1': chart1, 'chart2': chart2, 'chart3': chart3,
                                                         'chart4_ips': str(chart4['ips']).replace("\"", ""),
                                                         'chart4_processnum': chart4['processnum']})


'''单例测试'''


def testsingle(request):
    if request.method == 'POST':
        standard_file = request.POST.get('standard_file', '')
        test_file = request.POST.get('test_file', '')
        try:
            standard = readFile(standard_file)
            html_str = readFile(test_file)
            test = extract_content(html_str)
            ret = {'standard': standard, 'test': test}
        except:
            ret = {'error': 'error'}
        return HttpResponse(json.dumps(ret))
    else:
        return render_to_response('crawlermanage/test_single.html')


'''使用说明'''


def introduce(request):
    return render_to_response('crawlermanage/introduce.html')


def ecommercedata(request):
    taskid = request.GET.get('taskid')
    if taskid != None:
        goodslist = Goods.objects.filter(taskid=taskid)
        shoplist = Stores.objects.filter(taskid=taskid)
    page = request.GET.get('page')
    page2 = request.GET.get('page2')
    if page == None:
        page = 1
    if page2 == None:
        page2 = 1
    p = paging(goodslist, page, 10)
    p2 = paging(shoplist, page2, 10)
    return render(request, 'crawlermanage/ecommercedata.html', {'p': p, 'p2': p2})


def blogdata(request):
    taskid = request.GET.get('taskid')
    list = []
    if taskid != None:
        list = Blog.objects.filter(taskid=taskid)
    page = request.GET.get('page')
    if page == None:
        page = 1
    p = paging(list, page, 10)
    return render(request, 'crawlermanage/blogdata.html', locals())


def blogdetail(request):
    id = request.GET.get('id')
    if id == None:
        return
    blog = Blog.objects.get(id=id)
    if blog == None:
        return
    return render(request, 'crawlermanage/blogdetail.html', {'blog': blog})


def extractsinger(request):
    if request.method == 'POST':
        test_url = request.POST.get('test_url', '')
        title, atime, keywords, content = get_article_data(test_url)
        ret = {'title': title, 'time': atime, 'keywords': keywords, 'content': content}
        return HttpResponse(json.dumps(ret))
    return render_to_response('crawlermanage/extract_singer.html')


def extractmultiple(request):
    if request.method == 'POST':
        starturls = request.POST.get('starturls', '')
        webtype = request.POST.get('webtype', '')
        list_url = starturls.split('\n')

        # logger.info(li)
        if webtype == 'article':
            TempArticle.objects.delete()
            # list_id = []
            title_list = []
            time_list = []
            keywords_list = []
            article_list = []
            url_list = []
            for url in list_url:
                url = str(url)
                title, atime, keywords, content = get_article_data(url)
                # temp_article = TempArticle.objects.create(url=url, title=title, time=atime, keywords=keywords,
                #                                           article=content)
                title_list.append(title)
                time_list.append(atime)
                keywords_list.append(keywords)
                url_list.append(url)
                article_list.append(content)
                # list_id.append(str(temp_article['id']))
            # ret = {'webtype': webtype, 'urls': list_url, 'ids': (list_id)}
            ret = {'webtype': webtype,
                   'title': title_list, 'time': time_list, 'keywords': keywords_list,'urls':url_list, 'article': article_list}
            return HttpResponse(json.dumps(ret))
        elif(webtype == 'ecommerce_detail'):
            title_list = []
            price_list = []
            pic_url_list = []
            url_list=[]
            comment_list = []
            for url in list_url:
                url = str(url)
                goods_dict = get_goods_dict(url)
                title_list.append(goods_dict['title'])
                price_list.append(goods_dict['price'])
                pic_url_list.append(goods_dict['pic_url'])
                url_list.append(goods_dict['detail_url'])
                comment_list.append(goods_dict['comment_degree'])

            ret = {'webtype': webtype,
                   'title': title_list,'price':price_list,'pic_url':pic_url_list,'urls':url_list,'comment':comment_list}
            return HttpResponse(json.dumps(ret))

        elif (webtype == 'ecommerce_nav'):

            nav_list = []
            for url in list_url:
                methon,shop_nav = get_nav(url,0)
                nav_list.append(shop_nav)

            ret = {'webtype': webtype,'nav_list':nav_list,'urls':list_url}

            return HttpResponse(json.dumps(ret))
        else:
            res_goods_list = []
            for url in list_url:
                goods_list = get_goods_list(url)
                res_goods_list.append(goods_list)

            ret = {'webtype': webtype, 'res_goods_list': res_goods_list,'urls':list_url}

            return HttpResponse(json.dumps(ret))
    else:
        return render_to_response('crawlermanage/extract_multiple.html')


def temparticle(request):
    id = request.GET.get('id', '')
    news = TempArticle.objects.get(id=id)
    return render(request, 'crawlermanage/newsdetail.html', {'news': news})
