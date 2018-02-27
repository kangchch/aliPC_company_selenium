# -*- coding: utf-8 -*-

import sys
import os
import pymongo
import sys
import time
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from pymongo import MongoClient
import selenium.webdriver.support.ui as ui
from seleniumrequests import Chrome
from seleniumrequests import PhantomJS
from lxml import etree
import datetime
import re
import traceback
from function import *
from proxy import proxy
import requests
import signal
from selenium.webdriver.chrome.options import Options
class AliCompany():
    def __init__(self, browser_type='chrome', path=''):
        self.logger = logging.getLogger('AliCompany')
        self.proxy = proxy('chrome')
        # self.init_browser()

    def init_browser(self):
        self.browser = self.proxy.get_new_webdriver_with_proxy()
        opts = Options()
        opts.add_argument("--start-maximized")
        opts.add_argument("--headless")
        opts.add_argument("--disable-gpu")
        # self.browser = webdriver.Chrome("./chromedriver.exe",chrome_options=opts)
        self.wait = ui.WebDriverWait(self.browser, 20)

    def quit(self):
        try:
            if self.browser:
                self.browser.quit()
                self.browser = None
        except Exception, e:
            self.logger.warning("browser quit error:%s" % (str(e)))
        finally:
            self.browser = None
            # pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.quit()

    def get_company_item(self, username, record):
        if not username or not record: return {}
        url = "https://%s.1688.com/page/creditdetail.htm" %(username)
        while True:
            ## 0. open url
            try:
                self.init_browser()
                self.browser.get(url)
                logging.info('spider url [%s]' % url)
                wait = ui.WebDriverWait(self.browser, 30)
                wait.until(lambda browser: self.browser.find_element_by_xpath("//span[@class='support_label']|//*[@id='loginchina-wrapper']|//*[@id='main-frame-error']"))
            except Exception, e:
                #break
                pass
                # continue

            ## 1. judge page status from url
            i = {}

            cur_time = datetime.datetime.now()
            i['update_date'] = cur_time
            i['last_fetch_time'] = None

            i['web_status'] = get_errcode(self.browser.current_url)

            logging.info('[web_status] %s , url: %s', i['web_status'], self.browser.current_url)

            if i['web_status'] != ERR_CODE['OK']:
                if i['web_status'] == ERR_CODE['TEMP']:
                    logging.warning('get page failed! cur_url: %s', self.browser.current_url)
                    continue
                elif i['web_status'] == ERR_CODE['CLOSE']:
                    i['is_valid'] = False
                return i

            ## 2. judge page status is ok from xpath
            try:
                self.browser.find_element_by_xpath("//span[@class='support_label']")
            except:
                #i['web_status'] == ERR_CODE['TEMP']
                logging.warning('get page failed!')
                #return i
                #continue
            break

        ## 3. parse page content
        i['web_item_count'] = 0
        response = etree.HTML(self.browser.page_source)
        ## address 公司地址
        address = response.xpath("//span[@class='address_title']/text()")
        if address:
            address = re.findall(u'(?<=地址：).*', address[0], re.S)
            address = address[0].strip() if address else ''
        else:
            address = response.xpath("//a[@id='J_COMMON_CompanyInfoAddressMapBtn']/@map-mod-config")
            if address:
                address = re.findall(u'(?<=实际经营地址:).*?(?=","authPassDate)', address[0], re.S)
                address = address[0].strip() if address else ''
        i['address'] = address if address else record.get('address', '')
        logging.info('address [%s]' % i['address'])

        ## countryname provincename cityname
        ## 中国 浙江 金华 义乌市 稠洲街道城店路218号
        ## 中国 广东 佛山 南海区狮山镇罗村联和村小朗工业区一路6号厂房
        countryname = provincename = cityname = ''
        if address:
            items = address.split(' ')
            if len(items) > 3:
                countryname = items[0]
                provincename = items[1]
                cityname = items[2] if items[3].find(u'市') < 0 else items[3][:items[3].find(u'市')]
        i['countryname'] = countryname
        i['provincename'] = provincename
        i['cityname'] = cityname
        i['web_item_count'] += 4 if address else 0
        logging.info('countryname [%s-%s-%s]' % (i['countryname'], i['provincename'], i['cityname']))

        ## ali_industry 主营行业
        ali_params = response.xpath("//div[@id='J_CompanyDetailInfoList']//table")
        ali_params = ali_params[0] if ali_params else ''
        # print ali_params
        area = ali_params.xpath('string(.)') if ali_params else ''
        ali_industry = re.findall(u'(?<=主营行业).*?(?=是否提供加工定制)', area, re.S) if area else ''
        i['ali_industry'] = ali_industry[0].strip() if ali_industry else record.get('ali_industry', '')
        i['web_item_count'] += 1 if ali_industry else 0
        logging.info('ali_industry [%s]' % (i['ali_industry']))

        ## mainpro 主营产品或服务
        mainpro = re.findall(u'(?<=主营产品或服务).*?(?=主营行业)', area, re.S) if area else ''
        i['mainpro'] = mainpro[0].strip() if mainpro else record.get('mainpro', '')
        i['web_item_count'] += 1 if mainpro else 0
        logging.info('mainpro [%s]' % (i['mainpro']))

        ## kind 经营模式
        kind = re.findall(u'(?<=经营模式).*', area, re.S) if area else ''
        i['kind'] = kind[0].strip() if kind else record.get('kind', '')
        i['web_item_count'] += 1 if kind else 0
        logging.info('kind [%s]' % (i['kind']))

        ## ali_usetime 诚信通年限
        ali_usetime = response.xpath("//a[@class='icon icon-chengxintong']/text()")
        ali_usetime = re.findall(r'\d+', ali_usetime[0]) if ali_usetime else ''
        i['ali_usetime'] = int(ali_usetime[0]) if ali_usetime else record.get('ali_usetime', '-1')
        i['web_item_count'] += 1 if ali_usetime else 0
        logging.info('ali_usetime [%s]' % (i['ali_usetime']))

        ## contacter 联系人
        contacter = response.xpath("//span[@class='contact-info']/text()")
        contacter = re.findall(u'(?<=联系人：).*', contacter[0]) if contacter else ''
        i['contacter'] = contacter[0] if contacter else record.get('contacter', '')
        i['web_item_count'] += 1 if contacter else 0
        logging.info('contacter [%s]' % (i['contacter']))

        ## deals 交易量
        deals = response.xpath("//div[@id='J_CompanyTradeCreditRecord']/ul/li[1]/p[2]/text()")
        i['deals'] = int(deals[0]) if deals else record.get('deals', '-1')
        i['web_item_count'] += 1 if deals else 0
        logging.info('deals [%s]' % (i['deals']))

        ## duty 职位
        comment = response.xpath("//comment()")
        area = filter(lambda x:x.find(u'部门')>0, comment)
        department = re.findall(u'(?<=部门：</span>).*?(?=\</div>)', area[0], re.S) if area else ''
        title = re.findall(u'(?<=职位：</span>).*?(?=\</div>)', area[0], re.S) if area else ''
        duty = department[0].strip() if department else ''
        duty += ' ' + title[0].strip() if title else ''
        i['duty'] = duty.strip() if duty else record.get('duty', '')
        i['web_item_count'] += 1 if duty else 0
        logging.info('duty [%s]' % (i['duty']))

        ## introduce 企业介绍
        introduce = response.xpath("//p[@id='J_COMMON_CompanyInfoDetailInfo']/span/text()")
        i['introduce'] = introduce[0].strip() if introduce else record.get('introduce', '')
        i['web_item_count'] += 1 if introduce else 0
        logging.info('introduce [%s]' % (i['introduce']))

        ## register_date 通过中诚信专业认证时间
        register_date = response.xpath("//p[@class='register-title']/span[@class='title-remark']/text()")
        register_date = re.findall(r'\d+', register_date[0], re.S) if register_date else ''
        try:
            register_date = datetime.datetime.combine(datetime.date(int(register_date[0]), int(register_date[1]), int(register_date[2])), datetime.time.min)
        except Exception, e:
            register_date = None
        i['register_date'] = register_date if register_date else record.get('register_date', None)
        i['web_item_count'] += 1 if register_date else 0
        logging.info('register_date [%s]' % (i['register_date']))

        ## mp 手机
        mp = response.xpath("//div[@id='J_COMMON_CompanyInfoPhoneShow']/input[@name='hiddenMobileNo']/@value")
        i['mp'] = mp[0] if mp else ''
        if not i['mp']:
            mp = response.xpath("//div[@id='J_COMMON_CompanyInfoPhoneShow']/span[@class='tip-info phone-num']/text()")
            mp = re.findall(r'\d+', mp[0], re.S) if mp else ''
            i['mp'] = mp[0] if mp else record.get('mp', '')
        i['web_item_count'] += 1 if mp else 0
        logging.info('mp [%s]' % (i['mp']))

        ## telephone 固定电话
        telephone = response.xpath("//span[@class='tip-info phone-num']/text()")
        telephone = re.findall(r'\d+', telephone[0], re.S) if telephone else ''
        telephone = reduce(lambda x,y:x+'-'+y, telephone) if telephone else ''
        i['telephone'] = telephone if telephone else record.get('telephone', '')
        i['web_item_count'] += 1 if telephone else 0
        logging.info('telephone [%s]' % (i['telephone']))

        ## name 企业名称
        name = response.xpath("//div[@class='company']/h1[@class='company-name']/span[@class='name-text']/text()")
        i['name'] = name[0].strip() if name else record.get('name', '')
        i['web_item_count'] += 1 if name else 0
        logging.info('name [%s]' % (i['name']))

        ## memberid
        memberid = response.xpath("//head/meta[@name='mobile-agent']/@content")
        memberid = re.findall(r'(?<=winport/).*?(?=\.html)', memberid[0], re.S) if memberid else ''
        i['memberid'] = memberid[0] if memberid else record.get('memberid', '')
        logging.info('memberid [%s]' % (i['memberid']))

        ## uid
        # uid = re.findall(r'(?<=uid=).*?(?=&)', self.browser.page_source, re.S)
        # if uid and uid[0].strip():
        #     uid = uid[0] if uid[0][0] != '%' else uid[0].replace("%", "%25")
        # i['uid'] = uid if uid else record.get('uid', '')
        # async_url = 'http://member.1688.com/member/ajax/getMemberInfo.do?callback=jQuery17209556750445626676_1433833750505&loginId=undefined&member_login_id=' + str(i['uid']) + '&checkLogin=y&tracelog=member_card_open_undefined'
        # logging.info('async_url {%s}' % async_url)

        i['web_status'] = ERR_CODE['OK'] if i['web_item_count'] > 0 else ERR_CODE['IGNORE']

        return i


if __name__ == '__main__':
    reload(sys)
    sys.setdefaultencoding('utf-8')

    dirname, filename = os.path.split(os.path.realpath(__file__))
    log_file = dirname + '/logs/' + filename.replace('.py', '.log')
    logInit(log_file, logging.INFO, True)

    try:
        ali = AliCompany()
        mongo_db = MongoClient('192.168.60.65', 10010).ali_company

        while True:
            records = mongo_db.content_tbl.find({'web_status': ERR_CODE['IGNORE']},no_cursor_timeout = True
                                                ).sort([('insert_date', pymongo.DESCENDING)])
            #records_count = mongo_db.content_tbl.find({'web_status': ERR_CODE['BLOCK']},no_cursor_timeout = True
            #                                    ).sort([('insert_date', pymongo.DESCENDING)]).count()                                    
            #records = mongo_db.content_tbl.find({'web_status': {'$in': [ERR_CODE['BLOCK'], ERR_CODE['IGNORE']]}}
                                                 #).sort([('insert_date', pymongo.DESCENDING)])

            ##test
            # usernames = ['13735750275','shop1369155717627']
            # usernames = []
            #if records_count <= 0:
                #logging.info('not need spider username! speep 10')
                #time.sleep(10)
                #continue

            # logging.info('get new username [%d] ' % (records_count))

            for record in records:
                username = record['username']
                if not username:
                    continue
                try:
                    item = ali.get_company_item(username, record)
                except Exception as e:
                    logging.error('get body error! (%s)', traceback.print_exc())
                    continue

                if item['web_status'] == ERR_CODE['BLOCK']:
                    logging.warning('[BLOCK] %s', username)
                    ali.quit()
                    continue
                elif item['web_status'] == ERR_CODE['CLOSE']:
                    mongo_db.username.update_one({'username': username}, {'$set': {'status': USERNAMES_STATUS['FAILED'], 'is_charge': False}})
                    item['is_valid'] = False
                    mongo_db.content_tbl.update_one({'username': username}, {'$set': item})
                    logging.warning('[CLOSE] %s %d', username, item['web_status'])
                    ali.quit()
                    continue
                elif item['web_status'] == ERR_CODE['TEMP']:
                    mongo_db.content_tbl.update_one({'username': username}, {'$set': item})
                    logging.warning('[FAILED] %s %d ', username, item['web_status'])
                    ali.quit()
                    continue
                elif item['web_status'] != ERR_CODE['OK']:
                    mongo_db.content_tbl.update_one({'username': username}, {'$set': item})
                    logging.warning('[FAILED] %s %d ', username, item['web_status'])
                    ali.quit()
                    continue
                else:
                    item['is_valid'] = True
                    cur_time = datetime.datetime.now()
                    item['last_fetch_time'] = cur_time if ('ali_usetime', -1) > 0 else record['last_fetch_time']
                    item['update_date'] = cur_time
                    mongo_db.content_tbl.update({'username': username}, {'$set': item}, False, True)

                    memberid = item['memberid']
                    if memberid and not mongo_db.memberids.find_one({'memberid':memberid}):
                        mongo_db.memberids.insert({'memberid':memberid, 'username':username, 'insert_date':cur_time})
                    logging.info('[SUCCEED] update complete. %s web_item_count=%d,',username, item['web_item_count'])
                    ali.quit()
            mongo_db.close()    

    except Exception, e:
        logging.critical(str(traceback.format_exc()))
    finally:
        ali.quit()
        # time.sleep(1)
        # pass
