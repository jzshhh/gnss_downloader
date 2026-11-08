# -*- coding: utf-8 -*-
"""
GNSS 数据下载器（绿色便携版 / Portable）
GNSS Data Downloader

  1) IGS 站观测数据 + 广播星历 brdc   -> rinex/obs/yyyy/ddd, rinex/nav/yyyy
  2) 分析中心产品（存储库 -> 机构+系列 -> 产品）-> product/<机构>/<系列>/yyyy/ddd
  3) hfile（SOPAC / MIT，可增删源）    -> hfile/<源>/yyyy
  4) 区域网 RINEX（默认香港，可增删源） -> rinex/obs/yyyy/ddd

存储库：CDDIS / IGN / BKG / WHU(网页接口) / CODE-AIUB(网页接口)，
地址模板可在「数据源管理」查看修改；占位符：
  {YYYY} 4位年  {YY} 2位年  {DDD} 年积日  {GPSW} GPS周  {GPSD} 周内日
  {SSSS} 4位站名小写  {SSSSSSSSS} 9位站名大写   （小写写法兼容）

绿色版：仅依赖 Python 标准库；config.json / sources.json / history.json /
logs/ / cache/ 全部保存在程序目录。

开发者: 姜中山 (Zhongshan Jiang), 中山大学 (Sun Yat-sen University)
联系: jiangzhsh@mail.sysu.edu.cn
"""

import os
import re
import ssl
import sys
import json
import time
import base64
import hashlib
import queue
import threading
import datetime as dt
import urllib.request
import urllib.error
import urllib.parse
import http.cookiejar
import ftplib
from concurrent.futures import ThreadPoolExecutor

if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))


def _res_path(name):
    """资源路径：exe 旁外部文件优先（便于用户自行更新），否则用 exe 内置资源。"""
    ext = os.path.join(APP_DIR, name)
    if os.path.exists(ext):
        return ext
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, name)


def stations_txt_path():
    """IGS 站表：exe 旁外部文件优先（便于用户自行更新），否则用 exe 内置。"""
    ext = os.path.join(APP_DIR, 'igs_stations.txt')
    return ext if os.path.exists(ext) else _res_path('igs_stations.txt')


def geo_json_path():
    """测站坐标：exe 旁外部文件优先，否则用 exe 内置。"""
    ext = os.path.join(APP_DIR, 'igs_stations_geo.json')
    return ext if os.path.exists(ext) else _res_path('igs_stations_geo.json')

# ----------------------------------------------------------------------
# 界面语言（中文/English）
# ----------------------------------------------------------------------

_LANG = ['zh']           # 'zh' | 'en'

_STR = {
    'app_title': ('GNSS 数据下载器 (绿色便携版)', 'GNSS Data Downloader (Portable)'),
    'tab_igs': (' IGS观测+广播星历 ', ' IGS Obs + Nav '),
    'tab_prod': (' 分析中心产品 ', ' AC Products '),
    'tab_hfile': (' hfile ', ' hfile '),
    'tab_region': (' 区域网 ', ' Regional '),
    'tab_sources': (' 数据源管理 ', ' Sources '),
    'tab_settings': (' 设置 ', ' Settings '),
    'start_date': ('起始日期:', 'Start:'),
    'end_date': ('结束日期:', 'End:'),
    'yesterday': ('昨天', 'Yesterday'),
    'last7': ('近7天', 'Last 7d'),
    'last30': ('近30天', 'Last 30d'),
    'obs_files': ('观测文件', 'Obs files'),
    'nav_brdc': ('广播星历brdc', 'Broadcast nav (brdc)'),
    'repo': ('存储库:', 'Repository:'),
    'auto': ('自动', 'Auto'),
    'hint_igs': ('有RINEX3先下3；存储库可点「测速」选最快的',
                 'RINEX3 preferred; use Speed test to pick the fastest repo'),
    'hint_prod': ('点「下载」列勾选；机构行=整行切换；MGEX 2014年起·含北斗；2022-11起长命名自动适配',
                  'Click the Sel column; MGEX since 2014 (incl. BDS); long names auto-adapted'),
    'col_station': ('测站名(4位或9位)', 'Station (4/9-char)'),
    'col_dl': ('下载', 'Sel'),
    'col_repo_prod': ('存储库 / 机构+系列 / 产品', 'Repository / AC+Series / Product'),
    'btn_add': ('添加', 'Add'),
    'hf_net': ('网络:', 'Network:'),
    'es_btn': ('登录授权', 'Authorize'),
    'es_ok': ('已授权', 'Authorized'),
    'es_no': ('未授权', 'Not authorized'),
    'es_lg_tip': ('1. 点「打开浏览器」，登录你的 EarthScope 账号\n2. 确认页面显示的验证码与下面一致，点「确认」',
                  '1. Click "Open browser" and log in to EarthScope\n2. Check the code matches, then Approve'),
    'es_open': ('打开浏览器', 'Open browser'),
    'es_wait': ('等待授权 ...', 'Waiting for authorization ...'),
    'es_timeout': ('授权超时或失败，请重试', 'Authorization timed out / failed, please retry'),
    'btn_add_net': ('+ 新增区域网', '+ Add network'),
    'src_user': ('用户名(可空)', 'username (optional)'),
    'src_pass': ('密码(可空)', 'password (optional)'),
    'btn_del': ('删除', 'Remove'),
    'btn_selall': ('全选', 'All'),
    'btn_selnone': ('全不选', 'None'),
    'btn_import': ('从txt导入', 'Import txt'),
    'btn_paste': ('粘贴导入', 'Paste'),
    'btn_clear': ('清空', 'Clear'),
    'btn_map': ('地图选站', 'Map'),
    'btn_start': ('开始下载', 'Start'),
    'btn_stop': ('停止', 'Stop'),
    'threads': ('线程:', 'Threads:'),
    'ready': ('就绪', 'Ready'),
    'tab_log': (' 日志 ', ' Log '),
    'tab_stat': (' 本次统计 ', ' Statistics '),
    'btn_retry': ('重下失败项', 'Retry failed'),
    'btn_report': ('打开报告目录', 'Open reports'),
    'stat_idle': ('（运行一次下载后显示结果）', '(Run a download to see results)'),
    'col_file': ('文件 / 测站（含日期）', 'File / station (with date)'),
    'col_state': ('状态', 'Status'),
    'col_why': ('原因', 'Reason'),
    'st_ok': ('成功', 'OK'),
    'st_ne': ('不存在', 'Missing'),
    'st_fail': ('失败', 'Failed'),
    'st_skip': ('跳过', 'Skipped'),
    'cf_stopped': ('用户停止', 'Stopped by user'),
    'cf_notfound': ('服务器无此文件', 'No such file'),
    'cf_denied': ('权限被拒(需账号)', 'Denied (login required)'),
    'cf_server': ('服务器错误', 'Server error'),
    'cf_network': ('网络连不上', 'Network unreachable'),
    'cf_other': ('其他', 'Other'),
    'set_root': ('数据保存根目录', 'Data root directory'),
    'set_browse': ('浏览', 'Browse'),
    'set_threads': ('下载线程数', 'Download threads'),
    'set_retry': ('每文件重试次数', 'Retries per file'),
    'set_timeout': ('超时(秒)', 'Timeout (s)'),
    'set_proxy': ('代理(可空)', 'Proxy (optional)'),
    'set_ed_head': ('— NASA Earthdata 账号 (仅 CDDIS 需要, 保存于本地 config.json) —',
                    '— NASA Earthdata account (CDDIS only, stored locally) —'),
    'set_ed_user': ('Earthdata 用户名', 'Earthdata username'),
    'set_ed_pass': ('Earthdata 密码', 'Earthdata password'),
    'set_force': ('重新探测历史记录为"不存在"的文件 (默认跳过)',
                  'Re-check files marked "missing" in history'),
    'set_gunzip': ('下载后自动解压 .gz/.Z (内置 gzip.exe)',
                   'Auto-decompress .gz/.Z (built-in gzip.exe)'),
    'set_crx2rnx': ('下载后自动转换 .crx → .rnx (内置 crx2rnx.exe)',
                    'Auto-convert .crx to .rnx (built-in crx2rnx.exe)'),
    'set_save': ('保存设置', 'Save settings'),
    'set_proxy_hint': ('留空 = 直连（不使用系统代理）；连不上时可填入代理地址，如 http://127.0.0.1:7890',
                       'Blank = direct connection (system proxy NOT used); enter e.g. http://127.0.0.1:7890 if needed'),
    'test_ok': ('登录成功，CDDIS 可访问', 'Login OK, CDDIS reachable'),
    'test_badauth': ('账号或密码错误 (HTTP 401/403)', 'Wrong username or password (HTTP 401/403)'),
    'test_netfail': ('网络不通', 'Network unreachable'),
    'proxy_used': ('当前使用代理: %s', 'Using proxy: %s'),
    'proxy_direct': ('当前为直连（未使用代理）。若浏览器能打开而软件连不上，多为网络瞬时波动，可重试或在上方"代理"栏填写代理地址',
                     'Direct connection (no proxy). If your browser works, it is likely transient; retry or enter a proxy above'),
    'msg_quit_dl': ('正在下载中，确定退出？', 'Download in progress. Quit anyway?'),
    'msg_already': ('软件已经在运行中，请勿重复打开。\n（任务栏或托盘中找到已打开的窗口即可）',
                    'The app is already running. Please use the existing window.'),
    'set_test': ('测试 Earthdata 登录', 'Test Earthdata login'),
    'set_lang': ('界面语言 / Language', 'Language / 界面语言'),
    'set_speed': ('存储库测速', 'Speed test'),
    'tab_about': (' 关于 ', ' About '),
    'spd_col_rtt': ('延迟', 'Latency'),
    'spd_col_state': ('状态', 'Status'),
    'spd_testing': ('测速中…', 'Testing…'),
    'spd_fail': ('不可达(或需代理)', 'Unreachable (proxy?)'),
    'spd_use': ('采用最快', 'Use fastest'),
    'about_dev': ('开发者：姜中山 (Zhongshan Jiang)',
                  'Developer: Zhongshan Jiang (姜中山)'),
    'about_aff': ('单位：中山大学遥感科学与技术学院',
                  'Affiliation: School of Geospatial Engineering and Science, Sun Yat-sen University'),
    'about_src': ('数据源：CDDIS / IGN / BKG / 武汉大学(WHU) / CODE(AIUB)',
                  'Sources: CDDIS / IGN / BKG / WHU / CODE(AIUB)'),
    'about_manuals': ('说明书(点击打开)：', 'Manuals (click to open):'),
    'msg_pick_source': ('请先在树中选中一个数据源条目', 'Select a source item first'),
    'msg_tip': ('提示', 'Info'),
    'msg_err': ('错误', 'Error'),
    'msg_running': ('正在下载中', 'Download in progress'),
    'msg_need_ed': ('CDDIS 必须登录 NASA Earthdata 账号才能访问（未登录时文件会被误报为"不存在"）。\n\n请在「设置」页填写账号，或把存储库换成 WHU / IGN / BKG（均免账号）。',
                    'CDDIS requires a NASA Earthdata account; without it files are misreported as "missing".\n\nEnter the account in Settings, or switch the repository to WHU / IGN / BKG (no account needed).'),
    'msg_err_date': ('日期格式错误', 'Bad date format'),
    'msg_need_sta': ('请至少勾选一个测站', 'Select at least one station'),
    'msg_need_obsnav': ('请勾选「观测文件」或「广播星历brdc」',
                        'Check obs files or broadcast nav'),
    'msg_need_prod': ('请至少勾选一个产品', 'Check at least one product'),
    'msg_need_hfile': ('请至少启用一个 hfile 来源', 'Enable at least one hfile source'),
    'msg_need_region': ('请至少启用一个区域网并勾选测站',
                        'Enable a regional network and select stations'),
    'msg_no_retry': ('没有可重下的失败项（"不存在"的文件请在设置页打开强制重查）',
                     'Nothing retryable (for "missing" files enable re-check in Settings)'),
    'msg_map_missing': ('未找到 igs_stations_geo.json（应与程序放在同一目录）',
                        'igs_stations_geo.json not found (place it beside the program)'),
    'msg_confirm_del': ('删除选中的数据源？', 'Delete the selected source?'),
    'msg_confirm': ('确认', 'Confirm'),
    'msg_reset_src': ('恢复全部数据源为默认值？（你的修改和新增将丢失）',
                      'Reset all sources to defaults? (your edits will be lost)'),
    'msg_closed_add': ('产品类源为封闭集合，只能修改/删除，不能新增。区域网和 hfile 可以新增。',
                       'Product sources are a closed set (edit/delete only). Regional and hfile sources can be added.'),
    'grp_repo': ('存储库', 'Repositories'),
    'grp_ac': ('产品机构', 'Analysis centers'),
    'grp_ionex': ('电离层 IONEX', 'IONEX'),
    'grp_hfile': ('hfile', 'hfile'),
    'grp_region': ('区域网', 'Regional networks'),
    'grp_aiub': ('CODE/AIUB', 'CODE/AIUB'),
    'src_tip': ('占位符: {YYYY}=年 {YY}=2位年 {DDD}=年积日 {GPSW}=GPS周 {GPSD}=周内日 '
                '{SSSS}=4位站名 {SSSSSSSSS}=9位站名；双击或点「修改」编辑',
                'Placeholders: {YYYY} {YY} {DDD} {GPSW} {GPSD} {SSSS} {SSSSSSSSS}; double-click to edit'),
    'btn_ok': ('确定', 'OK'),
    'btn_cancel': ('取消', 'Cancel'),
    'fin': ('最终', 'Final'),
    'rap': ('快速', 'Rapid'),
    'ult': ('超快速', 'Ultra'),
    'mgex_tail': ('MGEX 2014起·含北斗', 'MGEX since 2014, incl. BDS'),
    'pt_orb': ('轨道 SP3', 'Orbit SP3'),
    'pt_clk': ('钟差 CLK', 'Clock CLK'),
    'pt_erp': ('ERP', 'ERP'),
    'pt_snx': ('SINEX 坐标', 'SINEX'),
    'pt_bia': ('BIA 偏差', 'Bias BIA'),
    'pt_ionex': ('电离层 IONEX', 'Ionosphere IONEX'),
    'cont_asia': ('亚洲', 'Asia'),
    'cont_europe': ('欧洲', 'Europe'),
    'cont_na': ('北美洲', 'North America'),
    'cont_sa': ('南美洲', 'South America'),
    'cont_africa': ('非洲', 'Africa'),
    'cont_oceania': ('大洋洲', 'Oceania'),
    'cont_antarctica': ('南极洲', 'Antarctica'),
    'cont_other': ('其他', 'Other'),
}


def tr(key):
    """界面文案翻译。找不到时返回 key 本身。"""
    s = _STR.get(key)
    if not s:
        return key
    return s[0] if _LANG[0] == 'zh' else s[1]


# ----------------------------------------------------------------------
# 基本工具
# ----------------------------------------------------------------------

def date_to_doy(y, m, d):
    return dt.date(y, m, d).timetuple().tm_yday


def date_to_gpsweek(y, m, d):
    gps0 = dt.date(1980, 1, 6)
    delta = (dt.date(y, m, d) - gps0).days
    return delta // 7, delta % 7


def iter_dates(s, e):
    d = dt.date(*[int(x) for x in s.split('-')])
    e0 = dt.date(*[int(x) for x in e.split('-')])
    while d <= e0:
        yield d
        d += dt.timedelta(days=1)


def _norm_proxy(p):
    """容错各种写法：127.0.0.1:7890 / http:127.0.0.1:7890 / http:/x 都归一成 http://..."""
    p = (p or '').strip()
    if not p:
        return ''
    if '://' in p:
        scheme, rest = p.split('://', 1)
        return scheme.lower() + '://' + rest
    p = p.replace('/', '')
    if p.lower().startswith(('http:', 'https:')):
        scheme, rest = p.split(':', 1)
        return scheme.lower() + '://' + rest
    return 'http://' + p


def enc(s):
    return base64.b64encode(s.encode('utf-8')).decode('ascii') if s else ''


def dec(s):
    try:
        return base64.b64decode(s.encode('ascii')).decode('utf-8') if s else ''
    except Exception:
        return ''


def placeholders(date, sta=None):
    """生成 URL 模板占位符字典（大小写两套都支持）"""
    yyyy = str(date.year)
    yy = yyyy[2:]
    ddd = '%03d' % date.timetuple().tm_yday
    W, dow = date_to_gpsweek(date.year, date.month, date.day)
    ph = {'YYYY': yyyy, 'YY': yy, 'DDD': ddd, 'GPSW': str(W), 'GPSD': str(dow),
          'yyyy': yyyy, 'yy': yy, 'ddd': ddd, 'W': str(W), 'dow': str(dow)}
    if sta:
        s4 = sta[:4].lower()
        s9 = sta[:9].upper() if len(sta.strip()) >= 9 else ''
        ph.update({'SSSS': s4, 'SSSSSSSSS': s9, 'sta4': s4, 'sta9': s9})
    return ph


def fmt_url(tpl, ph):
    """用占位符字典格式化 URL 模板，失败返回 None"""
    if not tpl:
        return None
    try:
        return tpl.format(**ph)
    except (KeyError, IndexError, ValueError):
        return None


def _dl_base(u):
    """下载基址：S3 列举型模板带 ?list-type&prefix=path，基址=主机+prefix"""
    if '?' not in u:
        return u
    base, qs = u.split('?', 1)
    pre = (urllib.parse.parse_qs(qs).get('prefix') or [''])[0]
    return base + pre


def tpl_needs_sta(tpl):
    return ('{SSSS' in tpl) or ('{sta' in tpl)


# ----------------------------------------------------------------------
# 国家码 -> 洲
# ----------------------------------------------------------------------

_CC_CONT = {}


def _fill_cc():
    def put(cont, codes):
        for c in codes.split():
            _CC_CONT[c] = cont
    put('asia', 'CHN HKG MAC TWN JPN KOR PRK IND THA MNG KAZ KGZ UZB TKM AFG IDN MYS '
                'PHL SGP VNM LAO KHM MMR LKA NPL BTN IRN IRQ ISR JOR KWT LBN PAK QAT '
                'SAU ARE ARM AZE BHR GEO OMN SYR TUR YEM BRN TLS RUS')
    put('europe', 'AUT BEL BGR CHE CZE DEU DNK ESP EST FIN FRA GBR GRC HRV HUN IRL ISL '
                  'ITA LTU LUX LVA MDA MKD MLT MNE NLD NOR POL PRT ROU SRB SVK SVN SWE '
                  'UKR ALA BLR BIH CYP ALB AND GIB FRO SJM')
    put('na', 'USA CAN MEX GRL GTM CUB DOM NIC SLV HND CRI PAN BLZ BES GLP MTQ SPM VIR '
              'BRB BHS HTI JAM TTO ABW ATG CYM DMA GRD KNA LCA MSR PRI TCA VCT')
    put('sa', 'ARG BOL BRA CHL COL ECU FLK GUF PER URY PRY SUR VEN GUY')
    put('africa', 'BEN CIV CPV DJI ETH GAB GHA KEN MAR MDG MUS NAM NGA REU SEN SHN SYC '
                  'UGA ZAF ZMB TZA DZA EGY LBY TUN AGO BWA CMR COD GIN MLI MOZ RWA SDN '
                  'SOM TCD ZWE BFA GMB LSO MWI NER')
    put('oceania', 'AUS NZL COK FJI FSM GUM KIR MHL NCL NIU NRU PNG PYF SLB TON TUV '
                   'VUT WLF WSM ASM PLW')
    put('antarctica', 'ATA ATF SGS HMD BVT')


_fill_cc()

CONT_ORDER = ['asia', 'europe', 'na', 'sa', 'africa', 'oceania', 'antarctica', 'other']
CHINA_CODES = ['CHN', 'HKG', 'MAC', 'TWN']


def load_stations_grouped(path):
    """读取 igs_stations.txt -> [(continent, [(line, cc), ...]), ...]
    中国(CHN/HKG/MAC/TWN)排在亚洲最前。"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    rows = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = re.search(r'\(([A-Z]{3})\)\s*$', line)
        cc = m.group(1) if m else ''
        rows.append((line, cc))
    groups = {c: [] for c in CONT_ORDER}
    for line, cc in rows:
        groups[_CC_CONT.get(cc, 'other')].append((line, cc))
    out = []
    for cont in CONT_ORDER:
        items = groups[cont]
        if not items:
            continue
        if cont == 'asia':
            china = [it for it in items if it[1] in CHINA_CODES]
            china.sort(key=lambda it: (CHINA_CODES.index(it[1]), it[0]))
            rest = sorted((it for it in items if it[1] not in CHINA_CODES),
                          key=lambda it: (it[1], it[0]))
            items = china + rest
        else:
            items.sort(key=lambda it: (it[1], it[0]))
        out.append((cont, items))
    return out


# ----------------------------------------------------------------------
# 配置 / 历史记录（绿色版：全部存程序目录）
# ----------------------------------------------------------------------

class Config:
    PATH = os.path.join(APP_DIR, 'config.json')

    DEFAULT = {
        'root_dir': APP_DIR,
        'threads': 4,
        'timeout': 30,
        'retry': 2,
        'earthdata_user': '',
        'earthdata_pass': '',
        'force_recheck_missing': False,
        'proxy': '',
        'lang': 'zh',
        'auto_gunzip': False,    # 下载后自动解压 .gz/.Z
        'auto_crx2rnx': False,   # 下载后自动 .crx -> .rnx
        'ui': {},                # 界面勾选记忆
    }

    def __init__(self):
        self.data = dict(self.DEFAULT)
        self.load()
        _LANG[0] = 'en' if self.data.get('lang') == 'en' else 'zh'

    def load(self):
        try:
            if os.path.exists(self.PATH):
                with open(self.PATH, 'r', encoding='utf-8') as f:
                    self.data.update(json.load(f))
        except Exception:
            pass

    def save(self):
        try:
            with open(self.PATH, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass


class History:
    PATH = os.path.join(APP_DIR, 'history.json')

    def __init__(self):
        self.data = {}
        self.lock = threading.Lock()
        self.load()

    def load(self):
        try:
            if os.path.exists(self.PATH):
                with open(self.PATH, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
        except Exception:
            self.data = {}

    def save(self):
        with self.lock:
            try:
                with open(self.PATH, 'w', encoding='utf-8') as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=1)
            except Exception:
                pass

    def get(self, rel):
        return self.data.get(rel)

    def set(self, rel, status, src=''):
        with self.lock:
            self.data[rel] = {'status': status,
                              'time': time.strftime('%Y-%m-%d %H:%M:%S'),
                              'src': src}
        self.save()


# ----------------------------------------------------------------------
# 数据源（sources.json）
# ----------------------------------------------------------------------

# 存储库 kind：
#   dir    - 传统目录型（HTTP/FTP 列目录，模板含占位符）
#   whuweb - 武大网页 JSON 接口（obsList/gbxlList/jmxlList + download?year=&id=）
#   aiubweb- AIUB 新站（php 列目录 + download 直链）
DEFAULT_SOURCES = {
    'centers': {
        'WHU': {
            'kind': 'whuweb',
            'api': 'http://www.igs.gnsswhu.cn/index.php/igs/',
            'obs': '', 'nav': '', 'prod': '', 'mgex': '', 'ion': ''},
        'BKG': {
            'kind': 'dir',
            'obs': 'https://igs.bkg.bund.de/root_ftp/IGS/obs/{YYYY}/{DDD}/',
            'nav': 'https://igs.bkg.bund.de/root_ftp/IGS/BRDC/{YYYY}/{DDD}/',
            'prod': 'https://igs.bkg.bund.de/root_ftp/IGS/products/{GPSW}/',
            'mgex': 'https://igs.bkg.bund.de/root_ftp/IGS/products/mgex/{GPSW}/',
            'ion': 'https://igs.bkg.bund.de/root_ftp/IGS/products/ionex/{YYYY}/{DDD}/'},
        'IGN': {
            'kind': 'dir',
            'obs': 'ftp://igs.ign.fr/pub/igs/data/{YYYY}/{DDD}/',
            'nav': 'ftp://igs.ign.fr/pub/igs/data/{YYYY}/brdc/',
            'prod': 'ftp://igs.ign.fr/pub/igs/products/{GPSW}/',
            'mgex': 'ftp://igs.ign.fr/pub/igs/products/mgex/{GPSW}/',
            'ion': 'ftp://igs.ign.fr/pub/igs/products/ionosphere/{YYYY}/{DDD}/'},
        'CDDIS': {
            'kind': 'dir',
            'obs': 'https://cddis.nasa.gov/archive/gnss/data/daily/{YYYY}/{DDD}/{YY}d/',
            'nav': 'https://cddis.nasa.gov/archive/gnss/data/daily/{YYYY}/brdc/',
            'prod': 'https://cddis.nasa.gov/archive/gnss/products/{GPSW}/',
            'mgex': 'https://cddis.nasa.gov/archive/gnss/products/mgex/{GPSW}/',
            'ion': 'https://cddis.nasa.gov/archive/gnss/products/ionex/{YYYY}/{DDD}/'},
        'CODE(AIUB)': {
            'kind': 'aiubweb',
            'api': 'https://code.aiub.unibe.ch/s3_script/aiub_s3_bucket_listing.php?path=',
            'obs': '', 'nav': '',
            'prod': 'https://www.aiub.unibe.ch/download/CODE/{YYYY}/',
            'mgex': 'https://www.aiub.unibe.ch/download/CODE_MGEX/CODE/{YYYY}/',
            'ion': ''},
    },
    'auto_order': ['WHU', 'BKG', 'IGN', 'CDDIS'],
    # 产品机构（封闭集合，可修改不可新增）。series: fin/rap/ult -> 产品列表
    'analysis_centers': [
        {'id': 'igs', 'name': 'IGS', 'mgex': False,
         'series': {'fin': ['orb', 'clk', 'erp', 'snx', 'bia'],
                    'rap': ['orb', 'clk', 'erp'],
                    'ult': ['orb', 'erp']}},
        {'id': 'cod', 'name': 'CODE', 'mgex': False,
         'series': {'fin': ['orb', 'clk', 'erp', 'snx', 'bia'],
                    'rap': ['orb', 'clk', 'erp'],
                    'ult': ['orb', 'erp']}},
        {'id': 'esa', 'name': 'ESA', 'mgex': False,
         'series': {'fin': ['orb', 'clk', 'erp', 'snx', 'bia'],
                    'rap': ['orb', 'clk', 'erp'],
                    'ult': ['orb', 'erp']}},
        {'id': 'jpl', 'name': 'JPL', 'mgex': False,
         'series': {'fin': ['orb', 'clk', 'erp', 'snx'],
                    'rap': ['orb', 'clk', 'erp']}},
        {'id': 'mit', 'name': 'MIT', 'mgex': False,
         'series': {'fin': ['orb', 'clk', 'erp', 'snx']}},
        {'id': 'wum', 'name': 'WHU', 'mgex': True,
         'series': {'fin': ['orb', 'clk', 'erp', 'snx', 'bia'],
                    'rap': ['orb', 'clk', 'erp']}},
        {'id': 'com', 'name': 'CODE', 'mgex': True,
         'series': {'fin': ['orb', 'clk', 'erp', 'bia', 'snx']}},
        {'id': 'gbm', 'name': 'GFZ', 'mgex': True,
         'series': {'fin': ['orb', 'clk', 'erp', 'snx', 'bia'],
                    'rap': ['orb', 'clk', 'erp']}},
        {'id': 'grm', 'name': 'GRGS', 'mgex': True,
         'series': {'fin': ['orb', 'clk', 'erp', 'bia']}},
        {'id': 'jam', 'name': 'JAXA', 'mgex': True,
         'series': {'fin': ['orb', 'clk', 'erp', 'bia']}},
        {'id': 'shm', 'name': 'SHAO', 'mgex': True,
         'series': {'fin': ['orb', 'clk', 'erp', 'bia']}},
    ],
    'ionex': [
        {'id': 'igsg', 'name': 'IGS'},
        {'id': 'codg', 'name': 'CODE'},
        {'id': 'whug', 'name': 'WHU'},
        {'id': 'esag', 'name': 'ESA'},
        {'id': 'jplg', 'name': 'JPL'},
    ],
    'aiub': {
        'url': 'https://www.aiub.unibe.ch/download/CODE/{YYYY}/',
        'items': [
            {'id': 'gim', 'name': '电离层 GIM (IONEX)'},
            {'id': 'ion', 'name': '电离层 ION (Bernese)'},
            {'id': 'bia', 'name': 'BIA 偏差 (Bernese)'},
            {'id': 'dcb', 'name': '月度 DCB (P1C1/P1P2)'},
        ]},
    'hfile': [
        {'id': 'sopacr20', 'name': 'SOPAC ITRF2020重处理(1992起)', 'by': 'day',
         'prefix': 'igs',
         'urls': ['https://garner.ucsd.edu/pub/hfilesR20/{YYYY}/{DDD}/']},
        {'id': 'mit', 'name': 'MIT(无前缀,服务器不稳时可在数据源管理改地址)', 'by': 'day',
         'prefix': '',
         'urls': ['https://chandler.mit.edu/ftp/hfiles/{YYYY}/{DDD}/']},
    ],
    'regional': [
        {'id': 'hk', 'name': '香港 SatRef',
         'templates': ['https://rinex.geodetic.gov.hk/rinex3/{YYYY}/{DDD}/{SSSS}/30s/',
                       'https://rinex.geodetic.gov.hk/rinex2/{YYYY}/{DDD}/{SSSS}/30s/'],
         'stations': ['hkcl', 'hkfn', 'hkkt', 'hklm', 'hkmw', 'hknp', 'hkpc',
                      'hkqt', 'hksc', 'hksl', 'hkss', 'hkst', 'hktb', 'hkth',
                      'hktw', 'hkws', 'kyc1', 't430']},
        {'id': 'sopac', 'name': '美国 SOPAC',
         'templates': ['https://garner.ucsd.edu/pub/rinex/{YYYY}/{DDD}/'],
         'stations': []},
        {'id': 'nz', 'name': '新西兰 GeoNet',
         'templates': ['https://data.geonet.org.nz/gnss/rinex/{YYYY}/{DDD}/'],
         'stations': []},
        {'id': 'ga', 'name': '澳大利亚 GA',
         'templates': ['https://ga-gnss-data-rinex-v1.s3.amazonaws.com/'
                       '?list-type=2&max-keys=1000&prefix=public/daily/{YYYY}/{DDD}/'],
         'stations': []},
        {'id': 'earthscope', 'name': '美国 EarthScope(需登录授权)', 'auth': 'esdevice',
         'templates': ['https://data.earthscope.org/archive/gnss/rinex/obs/{YYYY}/{DDD}/'],
         'stations': [], 'user': '', 'pass': ''},
    ],
}

PRODUCT_NAMES = {'orb': 'pt_orb', 'clk': 'pt_clk', 'erp': 'pt_erp',
                 'snx': 'pt_snx', 'bia': 'pt_bia'}
SERIES_IDS = ['fin', 'rap', 'ult']
SERIES_DIR = {'fin': 'final', 'rap': 'rapid', 'ult': 'ultra'}
# 长命名系列前缀（传统产品线 / MGEX 产品线）
LONG_PRES = {('fin', False): 'OPSFIN', ('rap', False): 'OPSRAP', ('ult', False): 'OPSULT',
             ('fin', True): 'MGXFIN', ('rap', True): 'MGXRAP', ('ult', True): 'MGXULT'}


class Sources:
    """数据源配置：sources.json 存在则整体采用用户的，否则用默认。"""

    PATH = os.path.join(APP_DIR, 'sources.json')

    def __init__(self):
        self.data = json.loads(json.dumps(DEFAULT_SOURCES))
        self.load()
        self._upgrade_dead_defaults()

    def load(self):
        try:
            if os.path.exists(self.PATH):
                with open(self.PATH, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
        except Exception:
            pass

    def save(self):
        try:
            with open(self.PATH, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def reset(self):
        self.data = json.loads(json.dumps(DEFAULT_SOURCES))
        self.save()

    def _upgrade_dead_defaults(self):
        """老配置自动迁移：WHU/AIUB 的 FTP 地址已失效，升级为网页通道。"""
        changed = False
        c = self.data.get('centers', {}).get('WHU')
        if c and c.get('kind') != 'whuweb':
            c.clear()
            c.update(json.loads(json.dumps(DEFAULT_SOURCES['centers']['WHU'])))
            changed = True
        a = self.data.get('aiub', {})
        if 'ftp.aiub.unibe.ch' in str(a.get('url', '')):
            a['url'] = DEFAULT_SOURCES['aiub']['url']
            changed = True
        if not a.get('items'):
            a['items'] = json.loads(json.dumps(DEFAULT_SOURCES['aiub']['items']))
            changed = True
        hf = self.data.get('hfile', [])
        hf_ids = [h.get('id') for h in hf]
        if hf_ids and ('sopaci20' in hf_ids
                       or ('sopac' in hf_ids and 'sopacr20' not in hf_ids)):
            self.data['hfile'] = json.loads(json.dumps(DEFAULT_SOURCES['hfile']))
            changed = True
        rg = self.data.setdefault('regional', [])
        have = {r.get('id') for r in rg}
        for r0 in DEFAULT_SOURCES['regional']:
            if r0['id'] not in have:
                rg.append(json.loads(json.dumps(r0)))
                changed = True
        for r in rg:                                   # EarthScope 改用 OAuth 授权
            if r.get('id') == 'earthscope' and r.get('auth') != 'esdevice':
                r['auth'] = 'esdevice'
                r['user'] = ''
                r['pass'] = ''
                r['name'] = '美国 EarthScope(需登录授权)'
                changed = True
        acs = self.data.get('analysis_centers', [])
        if acs and 'series' not in acs[0]:
            self.data['analysis_centers'] = json.loads(
                json.dumps(DEFAULT_SOURCES['analysis_centers']))
            changed = True
        if changed:
            self.save()

    # 便捷访问
    def centers(self):
        return self.data.get('centers', {})

    def auto_order(self):
        order = [c for c in (self.data.get('auto_order') or [])
                 if self.data['centers'].get(c, {}).get('kind') != 'aiubweb']
        return order or [k for k, v in self.centers().items() if v.get('kind') != 'aiubweb']

    def analysis_centers(self):
        return self.data.get('analysis_centers', [])

    def ionex(self):
        return self.data.get('ionex', [])

    def aiub(self):
        return self.data.get('aiub', {})

    def hfile(self):
        return self.data.get('hfile', [])

    def regional(self):
        return self.data.get('regional', [])

    def es_entry(self):
        for r in self.data.get('regional', []):
            if r.get('id') == 'earthscope':
                return r
        return None


# ----------------------------------------------------------------------
# 网络层：HTTP(S) 用 urllib，FTP 用 ftplib 连接池；目录列表带磁盘缓存
# ----------------------------------------------------------------------

_UA = 'Mozilla/5.0 (GNSS-Downloader)'
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE


class _Stopped(Exception):
    pass


ES_AUTH = {'domain': 'https://login.earthscope.org',
           'client_id': 'b9DtAFBd6QvMg761vI3YhYquNZbJX5G0',
           'audience': 'https://api.earthscope.org',
           'scope': 'offline_access'}


def _es_form_post(path, data, timeout=30):
    """EarthScope(Auth0) 表单 POST，返回 JSON。HTTPError 由调用方解析 error 字段。"""
    req = urllib.request.Request(
        ES_AUTH['domain'] + path,
        data=urllib.parse.urlencode(data).encode('utf-8'),
        headers={'User-Agent': _UA,
                 'Content-Type': 'application/x-www-form-urlencoded'})
    raw = urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx).read()
    return json.loads(raw.decode('utf-8', 'replace'))


class _BearerAuth(urllib.request.BaseHandler):
    """对登记的 OAuth 主机主动附带 Bearer token（EarthScope）。"""
    handler_order = 91

    def __init__(self, provider):
        self.provider = provider          # netloc -> token or None

    def http_request(self, req):
        try:
            tok = self.provider(urllib.parse.urlparse(req.full_url).netloc)
        except Exception:
            tok = None
        if tok and 'Authorization' not in req.headers:
            req.add_header('Authorization', 'Bearer ' + tok)
        return req
    https_request = http_request


class _PreemptiveAuth(urllib.request.BaseHandler):
    """对已登记主机主动附带 Basic 认证（应对跳转登录而非 401 挑战的网站）"""
    handler_order = 90

    def __init__(self, creds):
        self.creds = creds          # netloc -> 'Basic xxx'

    def http_request(self, req):
        if not req.full_url.startswith('https:'):
            return req                      # 明文 http 跳不送凭证
        tok = self.creds.get(urllib.parse.urlparse(req.full_url).netloc)
        if tok and 'Authorization' not in req.headers:
            req.add_header('Authorization', tok)
        return req
    https_request = http_request


class FtpClient:
    """FTP 连接池：每个工作线程对每台主机复用一条连接，支持 SIZE/续传。"""

    def __init__(self, timeout=30):
        self.timeout = timeout
        self._local = threading.local()

    @staticmethod
    def _parse(url):
        m = re.match(r'^ftp://([^/]+)(/.*)$', url)
        return m.group(1), m.group(2)

    def _conn(self, host):
        conns = getattr(self._local, 'conns', None)
        if conns is None:
            conns = {}
            self._local.conns = conns
        ftp = conns.get(host)
        if ftp is not None:
            try:
                ftp.voidcmd('NOOP')
                return ftp
            except Exception:
                try:
                    ftp.close()
                except Exception:
                    pass
        ftp = ftplib.FTP(host, timeout=self.timeout)
        ftp.login()
        ftp.voidcmd('TYPE I')
        conns[host] = ftp
        return ftp

    def listing(self, url):
        host, path = self._parse(url)
        try:
            ftp = self._conn(host)
            names = ftp.nlst(path)
            return sorted({n.split('/')[-1] for n in names if n and not n.endswith(('/.', '/..'))})
        except Exception:
            return []

    def measure(self, url, timeout=12):
        t0 = time.time()
        try:
            host, path = self._parse(url)
            old = self.timeout
            self.timeout = timeout
            try:
                self._conn(host).voidcmd('NOOP')
            finally:
                self.timeout = old
            return time.time() - t0
        except Exception:
            return None

    def download(self, url, dest, offset=0, stop_check=None, progress=None):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        tmp = dest + '.part'
        if offset == 0 and os.path.exists(tmp):
            offset = os.path.getsize(tmp)
        host, path = self._parse(url)
        try:
            ftp = self._conn(host)
            total = None
            try:
                total = ftp.size(path)
            except Exception:
                pass
            done = offset
            t0 = time.time()
            with open(tmp, 'ab' if offset else 'wb') as f:
                def _w(data):
                    nonlocal done
                    if stop_check and stop_check():
                        raise _Stopped()
                    f.write(data)
                    done += len(data)
                    if progress:
                        el = max(time.time() - t0, 0.01)
                        progress(done, total, done / el)
                ftp.retrbinary('RETR %s' % path, _w, blocksize=65536,
                               rest=offset if offset else None)
            os.replace(tmp, dest)
            return True, ''
        except _Stopped:
            return False, '已停止'
        except ftplib.error_perm as e:
            code = str(e)[:3]
            return False, 'HTTP %s' % ('404' if code == '550' else code)
        except Exception as e:
            return False, '%s: %s' % (type(e).__name__, str(e)[:80])


def _url_date(url):
    """从 URL 猜它对应的日期（/2024/031/ 或 /2380/ 形式），用于缓存过期判断。"""
    m = re.search(r'/(19|20)(\d{2})/(\d{3})(?:/|\.|$)', url)
    if m:
        try:
            return dt.date(int(m.group(1) + m.group(2)), 1, 1) + dt.timedelta(int(m.group(3)) - 1)
        except ValueError:
            return None
    m = re.search(r'/(1[6-9]\d{2}|2[0-9]\d{2})/?$', url)     # GPS 周目录
    if m:
        try:
            return dt.date(1980, 1, 6) + dt.timedelta(weeks=int(m.group(1)))
        except ValueError:
            return None
    m = re.search(r'[?&]path=[^&]*?((?:19|20)\d{2})', url)   # AIUB 年目录
    if m:
        return dt.date(int(m.group(1)), 7, 1)
    return None


class Http:
    def __init__(self, cfg, src=None):
        self.cfg = cfg
        self.src = src                # Sources，供读取各源自带账号
        self._opener_obj = None
        self._listing_mem = {}
        self._cache_lock = threading.Lock()
        self._ftp = None
        self._es_lock = threading.Lock()
        self.cache_dir = os.path.join(APP_DIR, 'cache')
        self.cache_ttl = 3600           # 近期数据缓存 1 小时；30 天前的永久

    def _opener(self):
        if self._opener_obj is not None:
            return self._opener_obj
        handlers = [urllib.request.HTTPSHandler(context=_ssl_ctx)]
        proxy = _norm_proxy(self.cfg.data.get('proxy'))
        if proxy:
            handlers.append(urllib.request.ProxyHandler({'http': proxy, 'https': proxy}))
        else:
            # 显式直连：不跟随系统代理，行为与"代理"栏所见一致
            handlers.append(urllib.request.ProxyHandler({}))
        user = self.cfg.data.get('earthdata_user', '')
        pw = dec(self.cfg.data.get('earthdata_pass', ''))
        if user and pw:
            pm = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            for host in ('https://urs.earthdata.nasa.gov', 'https://cddis.nasa.gov',
                         'https://urs.earthdata.nasa.gov/oauth/authorize'):
                pm.add_password(None, host, user, pw)
            handlers.append(urllib.request.HTTPBasicAuthHandler(pm))
            handlers.append(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        # 区域网/hfile 数据源自带的账号（Basic 型）
        creds = {}
        if user and pw:
            # Earthdata 必须 preemptive：URS 用 302 跳登录页，从不发 401 挑战
            tok = 'Basic ' + base64.b64encode(('%s:%s' % (user, pw)).encode()).decode()
            creds['urs.earthdata.nasa.gov'] = tok
            creds['cddis.nasa.gov'] = tok
        for coll in ('regional', 'hfile'):
            for s in self.src.data.get(coll, []):
                if s.get('auth') == 'esdevice':
                    continue                      # EarthScope 走 Bearer
                u = s.get('user', '')
                p = dec(s.get('pass', '')) if s.get('pass') else ''
                if not (u and p):
                    continue
                tok = 'Basic ' + base64.b64encode(('%s:%s' % (u, p)).encode()).decode()
                for tpl in (s.get('templates') or []) + (s.get('urls') or []):
                    nl = urllib.parse.urlparse(tpl).netloc
                    if nl:
                        creds[nl] = tok
        if creds:
            handlers.append(_PreemptiveAuth(creds))
        handlers.append(_BearerAuth(self.bearer_token))
        self._opener_obj = urllib.request.build_opener(*handlers)
        return self._opener_obj

    def _es_tokens(self):
        e = self.src.es_entry() if self.src else None
        if not e or not e.get('es_token'):
            return None
        try:
            return json.loads(dec(e['es_token']))
        except Exception:
            return None

    def bearer_token(self, netloc):
        """OAuth Bearer 提供器：仅 EarthScope；过期自动用 refresh token 续期。"""
        if netloc != 'data.earthscope.org' or self.src is None:
            return None
        with self._es_lock:
            t = self._es_tokens()
            if not t or not t.get('access'):
                return None
            if time.time() < t.get('exp', 0):
                return t['access']
            try:
                r = _es_form_post('/oauth/token', {
                    'grant_type': 'refresh_token',
                    'client_id': ES_AUTH['client_id'],
                    'refresh_token': t.get('refresh', '')})
                nt = {'access': r['access_token'],
                      'refresh': r.get('refresh_token') or t.get('refresh', ''),
                      'exp': time.time() + int(r.get('expires_in', 86400)) - 120}
                e = self.src.es_entry()
                if e is not None:
                    e['es_token'] = enc(json.dumps(nt))
                    self.src.save()
                return nt['access']
            except Exception:
                return None

    def ftp(self):
        if self._ftp is None:
            self._ftp = FtpClient(timeout=int(self.cfg.data.get('timeout', 30)))
        return self._ftp

    def reset(self):
        self._opener_obj = None
        self._ftp = None
        with self._cache_lock:
            self._listing_mem.clear()

    def measure(self, url, timeout=12):
        """小流量测速，返回秒数；不可达返回 None"""
        if url.startswith('ftp://'):
            return self.ftp().measure(url, timeout)
        t0 = time.time()
        try:
            req = urllib.request.Request(url, headers={'User-Agent': _UA})
            r = self._opener().open(req, timeout=timeout)
            r.read(2048)
            r.close()
            return time.time() - t0
        except Exception:
            return None

    def _tmo(self, url, timeout):
        """NASA(CDDIS/URS) 链路慢且偶发丢包，超时放宽到至少 60 秒"""
        t = int(timeout or self.cfg.data['timeout'])
        if 'nasa.gov' in url:
            return max(t, 60)
        return t

    def get_bytes(self, url, timeout=None):
        req = urllib.request.Request(url, headers={'User-Agent': _UA})
        return self._opener().open(req, timeout=self._tmo(url, timeout)).read()

    def post_json(self, url, payload, timeout=None):
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'),
                                     headers={'User-Agent': _UA,
                                              'Content-Type': 'application/json'})
        return json.load(self._opener().open(req, timeout=timeout or self.cfg.data['timeout']))

    # ---------- 目录列表（内存 + 磁盘两级缓存） ----------
    def _cache_path(self, url):
        return os.path.join(self.cache_dir, hashlib.md5(url.encode('utf-8')).hexdigest() + '.json')

    def _cache_get(self, url):
        p = self._cache_path(url)
        try:
            if not os.path.exists(p):
                return None
            with open(p, 'r', encoding='utf-8') as f:
                obj = json.load(f)
            d = _url_date(url)
            if d is not None and (dt.date.today() - d).days > 30:
                return obj.get('names')            # 老数据永久有效
            if time.time() - obj.get('t', 0) < self.cache_ttl:
                return obj.get('names')
        except Exception:
            pass
        return None

    def _cache_put(self, url, names):
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(self._cache_path(url), 'w', encoding='utf-8') as f:
                json.dump({'t': time.time(), 'names': names}, f)
        except Exception:
            pass

    def listing(self, url):
        """目录列表 -> 文件名集合（HTTP HTML / FTP NLST），两级缓存"""
        with self._cache_lock:
            if url in self._listing_mem:
                return self._listing_mem[url]
        cached = self._cache_get(url)
        if cached is not None:
            cached = sorted({n.strip() for n in cached if n and n.strip()})
            with self._cache_lock:
                self._listing_mem[url] = cached
            return cached
        names = []
        if url.startswith('ftp://'):
            for _try in range(2):
                names = self.ftp().listing(url)
                if names:
                    break
        else:
            es_list = 'data.earthscope.org' in url
            fetch_url = (url + ('&' if '?' in url else '?') + 'list'
                         if es_list else url)
            for _try in range(3):               # 慢链路偶发超时：最多试 3 次
                try:
                    html = self.get_bytes(fetch_url).decode('utf-8', 'ignore')
                    if es_list:
                        # EarthScope ?list：纯文本，每行 "文件名 大小 日期 时间戳"；
                        # 未授权时被跳到登录页(HTML)，此时留空
                        if not html.lstrip().startswith('<'):
                            for ln in html.splitlines():
                                ln = ln.strip()
                                if ln:
                                    names.append(ln.split()[0])
                            names = sorted(set(names))
                    elif html.lstrip()[:100].startswith('<?xml') and '<ListBucketResult' in html:
                        # S3 XML 列表（如澳大利亚 GA），支持翻页
                        keys = re.findall(r'<Key>([^<]+)</Key>', html)
                        tok = re.search(r'<NextContinuationToken>([^<]+)</NextContinuationToken>', html)
                        pages = 0
                        while tok and pages < 9:
                            pages += 1
                            joiner = '&' if '?' in url else '?'
                            more = self.get_bytes(
                                url + joiner + 'continuation-token='
                                + urllib.parse.quote(tok.group(1))).decode('utf-8', 'ignore')
                            keys += re.findall(r'<Key>([^<]+)</Key>', more)
                            tok = re.search(r'<NextContinuationToken>([^<]+)</NextContinuationToken>', more)
                        names = sorted({k.rstrip('/').split('/')[-1] for k in keys})
                    else:
                        for h in re.findall(r'href\s*=\s*["\']([^"\']+)["\']', html, re.I):
                            if h.startswith(('?', '#', 'mailto:')):
                                continue
                            name = h.split('?')[0].rstrip('/').split('/')[-1]
                            if not name or name.lower() == 'parent directory':
                                continue
                            names.append(urllib.parse.unquote(name))
                        names = sorted(set(names))
                    break
                except urllib.error.HTTPError as e:
                    if e.code in (401, 403):
                        break                   # 权限问题重试无意义
                    names = []
                except Exception:
                    names = []
        names = sorted({n.strip() for n in names if n and n.strip()})
        with self._cache_lock:
            self._listing_mem[url] = names
        if names:
            self._cache_put(url, names)
        return names

    def download(self, url, dest, timeout=None, stop_check=None, progress=None):
        """统一下载入口（http/ftp），支持 .part 断点续传。返回 (ok, err)。"""
        if url.startswith('ftp://'):
            return self.ftp().download(url, dest, stop_check=stop_check, progress=progress)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        tmp = dest + '.part'
        offset = os.path.getsize(tmp) if os.path.exists(tmp) else 0
        headers = {'User-Agent': _UA}
        if offset:
            headers['Range'] = 'bytes=%d-' % offset
        req = urllib.request.Request(url, headers=headers)
        t0 = time.time()
        try:
            r = self._opener().open(req, timeout=self._tmo(url, timeout))
            # 未登录被跳到登录页或返回 HTML：不能当成数据存下来。
            # 注意 WHU download 接口误标 Content-Type: text/html，
            # 但内容是 gzip 数据——需看内容魔数再判定。
            final_path = urllib.parse.urlparse(r.geturl()).path
            if '/login' in final_path:
                r.close()
                return False, 'HTTP 401 需账号(跳登录页)'
            ctype = (r.headers.get('Content-Type') or '').lower()
            head = r.read(512)
            if (ctype.startswith('text/html') and not head.startswith(b'\x1f\x8b')
                    and (head.lstrip()[:1] == b'<' or b'<html' in head[:512].lower())):
                r.close()
                return False, 'HTTP 401 需账号(跳登录页)'
            code = getattr(r, 'status', 200)
            if offset and code != 206:      # 服务器不支持续传，重下
                offset = 0
            total = r.headers.get('Content-Length')
            total = (int(total) + offset) if total else None
            done = offset
            with r, open(tmp, 'ab' if offset else 'wb') as f:
                if head:
                    f.write(head)
                    done += len(head)
                while True:
                    if stop_check and stop_check():
                        raise _Stopped()
                    chunk = r.read(1024 * 64)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress:
                        el = max(time.time() - t0, 0.01)
                        progress(done, total, done / el)
            os.replace(tmp, dest)
            return True, ''
        except _Stopped:
            return False, '已停止'
        except urllib.error.HTTPError as e:
            return False, 'HTTP %s' % e.code
        except Exception as e:
            return False, '%s: %s' % (type(e).__name__, str(e)[:80])


# ----------------------------------------------------------------------
# 武大网页通道：查询 JSON 接口 + id 下载
# ----------------------------------------------------------------------

class WhuWeb:
    """igs.gnsswhu.cn 网页接口。
    查询: POST {api}obsList / gbxlList / jmxlList  (JSON)
    下载: GET  {api}download?year=YYYY&id=NNN
    """

    def __init__(self, http, api):
        self.http = http
        self.api = api if api.endswith('/') else api + '/'

    def _query(self, ep, data, limit=2000, max_pages=25):
        rows = []
        start = 0
        for _ in range(max_pages):
            try:
                r = self.http.post_json(self.api + ep,
                                        {'data': data, 'start': start, 'limit': limit},
                                        timeout=40)
            except Exception:
                break
            if r.get('result_code') != 0:
                break
            batch = r.get('rows') or []
            rows += batch
            total = r.get('total') or 0
            start += len(batch)
            if not batch or start >= total:
                break
        return rows

    def obs(self, stations4, d1, d2):
        """站点4位小写列表；跨年自动拆分查询。"""
        out = []
        for y in range(int(d1[:4]), int(d2[:4]) + 1):
            s = max(d1, '%d-01-01' % y)
            e = min(d2, '%d-12-31' % y)
            out += self._query('obsList', {'type': 'obs', 'gs': 'o',
                                           'site': list(stations4), 'filename': '',
                                           'start_time': s, 'end_time': e})
        return out

    def nav(self, d1, d2):
        return self._query('gbxlList', {'type': 'gbxl', 'filename': 'brdc',
                                        'start_time': d1, 'end_time': d2})

    def products(self, prefix, d1, d2):
        """跨年拆分查询：跨年区间+filename 过滤会触发服务器 500。"""
        out = []
        for y in range(int(d1[:4]), int(d2[:4]) + 1):
            s = max(d1, '%d-01-01' % y)
            e = min(d2, '%d-12-31' % y)
            out += self._query('jmxlList', {'type': 'jmxl', 'filename': prefix,
                                            'start_time': s, 'end_time': e})
        return out

    def url_of(self, row):
        return '%sdownload?year=%s&id=%s' % (self.api, row.get('year'), row.get('id'))


# ----------------------------------------------------------------------
# AIUB 网页通道：php 列目录 + download 直链
# ----------------------------------------------------------------------

class AiubWeb:
    """code.aiub.unibe.ch 列目录接口。路径形如 'CODE/2025'、'CODE_MGEX/CODE/2025'。"""

    def __init__(self, http, api, download_base='https://www.aiub.unibe.ch/download/'):
        self.http = http
        self.api = api                     # ...aiub_s3_bucket_listing.php?path=
        self.base = download_base

    def listing(self, sub_path):
        """sub_path 形如 'CODE/2025'，返回文件名列表；None=不可达。"""
        url = self.api + urllib.parse.quote(sub_path, safe='')
        try:
            html = self.http.get_bytes(url, timeout=40).decode('utf-8', 'ignore')
        except Exception:
            return None
        names = []
        for h in re.findall(r'href\s*=\s*["\']([^"\']+)["\']', html, re.I):
            if 'download/' in h:
                name = h.rstrip('/').split('/')[-1]
                if name:
                    names.append(urllib.parse.unquote(name))
        return sorted(set(names))

    def file_url(self, sub_path, fname):
        return self.base + sub_path + '/' + fname


# ----------------------------------------------------------------------
# 下载任务与引擎
# ----------------------------------------------------------------------

class Task:
    __slots__ = ('urls', 'dest', 'rel', 'label')

    def __init__(self, urls, dest, rel, label):
        self.urls = urls
        self.dest = dest
        self.rel = rel
        self.label = label


def classify_fail(err):
    """失败原因归类，返回 key：stopped/notfound/denied/server/network/other"""
    e = str(err)
    if e == '已停止':
        return 'stopped'
    if e.startswith('HTTP 404') or e.startswith('HTTP 550'):
        return 'notfound'
    if e.startswith(('HTTP 401', 'HTTP 403')):
        return 'denied'
    if e.startswith('HTTP 5'):
        return 'server'
    low = e.lower()
    if any(k in low for k in ('timeout', 'timed out', 'refused', 'unreachable',
                              'getaddrinfo', 'name or service', 'eof', 'connection',
                              'reset', 'temporarily')):
        return 'network'
    return 'other'


class Engine:
    def __init__(self, cfg, hist, http, log_cb, prog_cb, fprog_cb=None):
        self.cfg = cfg
        self.hist = hist
        self.http = http
        self.log = log_cb
        self.prog = prog_cb
        self.fprog = fprog_cb          # (label, done, total, speed)
        self.stop_event = threading.Event()
        self.results = {'ok': [], 'failed': [], 'notexist': [], 'skipped': []}
        self.task_map = {}             # rel -> Task（供重下失败项）
        self._fprog_last = {}

    def _post_process(self, dest):
        """下载成功后按设置自动解压/转换。"""
        if not os.path.exists(dest):
            return
        low = dest.lower()
        if low.endswith('.crx.gz') or low.endswith('.crx.z'):
            if self.cfg.data.get('auto_gunzip'):
                dest = self._gunzip(dest)
            if dest and self.cfg.data.get('auto_crx2rnx') and dest.lower().endswith('.crx'):
                self._crx2rnx(dest)
            return
        if low.endswith('.gz') or low.endswith('.z'):
            if self.cfg.data.get('auto_gunzip'):
                self._gunzip(dest)
            return
        if low.endswith('.crx') and self.cfg.data.get('auto_crx2rnx'):
            self._crx2rnx(dest)

    @staticmethod
    def _gunzip(path):
        gz = _res_path('gzip.exe')
        if not os.path.exists(gz):
            return None
        try:
            import subprocess
            r = subprocess.run([gz, '-d', '-f', path],
                               capture_output=True, timeout=120)
            out = os.path.splitext(path)[0]
            if r.returncode == 0 and os.path.exists(out):
                return out
        except Exception:
            pass
        return None

    @staticmethod
    def _crx2rnx(path):
        exe = _res_path('crx2rnx.exe')
        if not os.path.exists(exe):
            return
        try:
            import subprocess
            subprocess.run([exe, path], capture_output=True, timeout=60)
        except Exception:
            pass

    def run(self, tasks):
        self.stop_event.clear()
        self.task_map = {t.rel: t for t in tasks}
        todo = []
        n_skip = 0
        force = self.cfg.data.get('force_recheck_missing', False)
        for t in tasks:
            h = self.hist.get(t.rel)
            if h and h.get('status') == 'ok' and os.path.exists(t.dest) and os.path.getsize(t.dest) > 0:
                self.results['skipped'].append((t.label, '已存在'))
                n_skip += 1
                continue
            if h and h.get('status') == 'notexist' and not force:
                self.results['skipped'].append((t.label, '历史记录:不存在'))
                n_skip += 1
                continue
            if os.path.exists(t.dest) and os.path.getsize(t.dest) > 0:
                self.hist.set(t.rel, 'ok', 'local')
                self.results['skipped'].append((t.label, '已存在'))
                n_skip += 1
                continue
            todo.append(t)
        self.log('任务总数 %d，跳过 %d（已存在/历史不存在），实际下载 %d'
                 % (len(tasks), n_skip, len(todo)))
        # 跨源分流：轮转候选地址顺序，让并发任务打到不同镜像
        for i, t in enumerate(todo):
            if len(t.urls) > 1:
                k = i % len(t.urls)
                t.urls = t.urls[k:] + t.urls[:k]
        total = max(len(todo), 1)
        done = [0]
        lock = threading.Lock()

        def work(t):
            if self.stop_event.is_set():
                return
            status, src = self._fetch(t)
            with lock:
                done[0] += 1
                self.prog(done[0], total)
            if self.fprog:
                self.fprog(t.label, -1, -1, 0)       # 结束标记
            if status == 'ok':
                self.results['ok'].append(t.label)
                self.log('[成功] %s  <-  %s' % (t.label, src))
                self._post_process(t.dest)
            elif status == 'notexist':
                self.results['notexist'].append(t.label)
                self.log('[不存在] %s' % t.label)
            else:
                self.results['failed'].append((t.label, src, t.rel))
                self.log('[失败] %s  (%s)' % (t.label, src))

        with ThreadPoolExecutor(max_workers=max(1, int(self.cfg.data.get('threads', 4)))) as ex:
            list(ex.map(work, todo))
        self.write_report()
        self.log('完成：成功 %d / 失败 %d / 不存在 %d / 跳过 %d'
                 % (len(self.results['ok']), len(self.results['failed']),
                    len(self.results['notexist']), len(self.results['skipped'])))

    def _fetch(self, t):
        retry = int(self.cfg.data.get('retry', 2))
        saw_404 = False
        last_err = ''

        def progress(done_b, total_b, speed):
            if not self.fprog:
                return
            now = time.time()
            if now - self._fprog_last.get(t.rel, 0) < 0.25:
                return
            self._fprog_last[t.rel] = now
            self.fprog(t.label, done_b, total_b or -1, speed)

        for url in t.urls:
            if self.stop_event.is_set():
                return 'failed', '已停止'
            for _ in range(retry + 1):
                ok, err = self.http.download(url, t.dest,
                                             stop_check=self.stop_event.is_set,
                                             progress=progress)
                if ok:
                    self.hist.set(t.rel, 'ok', url)
                    return 'ok', url
                last_err = err
                if err == '已停止':
                    return 'failed', err
                if err.startswith(('HTTP 404', 'HTTP 550')):
                    saw_404 = True
                    break
                if err.startswith('HTTP 4'):
                    break                    # 401/403 等：重试无意义，也不算不存在
                if self.stop_event.is_set():
                    return 'failed', '已停止'
                time.sleep(1.5)
        st = 'notexist' if saw_404 else 'failed'
        self.hist.set(t.rel, st, t.urls[0])
        return st, last_err

    def retryable_failed(self):
        """可重下的失败项（网络类），返回 Task 列表"""
        out = []
        for item in self.results['failed']:
            label, err, rel = item
            if classify_fail(err) in ('network', 'server', 'other'):
                t = self.task_map.get(rel)
                if t:
                    out.append(t)
        return out

    def write_report(self):
        os.makedirs(os.path.join(APP_DIR, 'logs'), exist_ok=True)
        p = os.path.join(APP_DIR, 'logs',
                         'report_%s_%03d.txt' % (time.strftime('%Y%m%d_%H%M%S'),
                                                 int(time.time() * 1000) % 1000))
        with open(p, 'w', encoding='utf-8') as f:
            f.write('GNSS 数据下载统计报告  %s\n' % time.strftime('%Y-%m-%d %H:%M:%S'))
            f.write('=' * 60 + '\n')
            for title, key in (('成功', 'ok'), ('不存在(服务器无此文件)', 'notexist'),
                               ('失败(需重下)', 'failed'), ('跳过', 'skipped')):
                items = self.results[key]
                f.write('\n【%s】 %d 项\n' % (title, len(items)))
                f.write('-' * 60 + '\n')
                for it in items:
                    if isinstance(it, tuple):
                        f.write('%s    %s\n' % (it[0], it[1]))
                    else:
                        f.write('%s\n' % it)
        self.log('统计报告已保存: %s' % p)


# ----------------------------------------------------------------------
# 任务生成
# ----------------------------------------------------------------------

RE_R2_OBS = re.compile(r'^[a-z0-9]{4}\d{3}0\.\d{2}[do](\.(z|gz))?$', re.I)
RE_R3_OBS = re.compile(r'_[A-Z]?O\.(CRX|RNX)(\.GZ)?$', re.I)
RE_FN_DATE = re.compile(r'_((?:19|20)\d{2})(\d{3})(\d{2})00_')
ULT_HOURS = ['00', '06', '12', '18']
# 长命名产品关键字（可能多个候选）
LONG_KEYS = {'orb': ('_ORB.SP3',), 'clk': ('_CLK.CLK',), 'erp': ('_ERP.ERP',),
             'snx': ('_CRD.SNX', '_SOL.SNX'), 'bia': ('_BIA.', 'SB.BIA')}
LEGACY_EXT = {'orb': ('.sp3', '.eph'), 'clk': ('.clk',), 'erp': ('.erp',),
              'snx': ('.snx', '.ssc'), 'bia': ('.bia', '.bsx')}


def is_r3_obs(name):
    return len(name) > 20 and bool(RE_R3_OBS.search(name.upper()))


class TaskBuilder:
    def __init__(self, http, cfg, src, log, stop_event=None):
        self.http = http
        self.cfg = cfg
        self.src = src
        self.log = log
        self.root = cfg.data['root_dir']
        self.stop = stop_event or threading.Event()
        self._whu = {}
        self._aiub = {}

    def _stopped(self):
        return self.stop.is_set()

    def whu(self, ck):
        if ck not in self._whu:
            self._whu[ck] = WhuWeb(self.http, self.src.centers()[ck].get('api', ''))
        return self._whu[ck]

    def aiub(self, ck='CODE(AIUB)'):
        if ck not in self._aiub:
            c = self.src.centers().get(ck, {})
            self._aiub[ck] = AiubWeb(self.http, c.get('api', ''))
        return self._aiub[ck]

    def _cks(self, center):
        """存储库顺序：固定单库，或自动模式（优先用测速排序结果）"""
        if center != '自动':
            return [center]
        order = self.cfg.data.get('_order') or self.src.auto_order()
        return [c for c in order if c in self.src.centers()] or list(self.src.centers().keys())

    def _parallel_days(self, d1, d2, fn, workers=None):
        """按天并行生成任务，结果保持日期顺序。fn(date) -> (tasks, missing)"""
        dates = list(iter_dates(d1, d2))
        results = [None] * len(dates)
        nwork = workers or max(1, min(4, int(self.cfg.data.get('threads', 4))))

        def call(i, date):
            if self._stopped():
                return ([], [])
            return fn(date)

        with ThreadPoolExecutor(max_workers=nwork) as ex:
            futs = {ex.submit(call, i, d): i for i, d in enumerate(dates)}
            for fut, i in futs.items():
                try:
                    results[i] = fut.result()
                except Exception as e:
                    results[i] = ([], ['生成任务出错: %s' % str(e)[:80]])
        tasks, missing = [], []
        for r in results:
            if r:
                tasks += r[0]
                missing += r[1]
        return tasks, missing

    # ================= 模块1: IGS 观测 + brdc =================
    def _find_obs_in_listing(self, names, sta):
        sta4 = sta[:4].lower()
        sta9 = sta.upper() if len(sta.strip()) >= 9 else None
        r2 = None
        for n in names:
            nu = n.upper()
            if is_r3_obs(n):
                if (sta9 and n.startswith(sta9)) or (not sta9 and nu.startswith(sta4.upper())):
                    return n
            elif RE_R2_OBS.match(n) and n[:4].lower() == sta4:
                r2 = r2 or n
        return r2

    def build_igs(self, d1, d2, stations, want_obs, want_nav, center):
        cks = self._cks(center)
        centers = self.src.centers()
        dates = list(iter_dates(d1, d2))
        tasks, missing = [], []
        # (sta4, date) 待满足集合
        pending = {(s[:4].lower(), d) for s in stations for d in dates} if want_obs else set()
        nav_pending = set(dates) if want_nav else set()
        sta_disp = {s[:4].lower(): s for s in stations}

        for ck in cks:
            if self._stopped() or (not pending and not nav_pending):
                break
            kind = centers.get(ck, {}).get('kind', 'dir')
            if kind == 'whuweb':
                self._igs_whu(ck, d1, d2, pending, nav_pending, tasks, sta_disp)
            elif kind == 'dir':
                self._igs_dir(ck, cks, dates, pending, nav_pending, tasks)

        for sta4, d in sorted(pending, key=lambda x: (x[1], x[0])):
            missing.append('%s %s/%03d 观测(各库均无)' % (sta_disp.get(sta4, sta4), d.year,
                                                        d.timetuple().tm_yday))
        for d in sorted(nav_pending):
            missing.append('brdc %s/%03d (各库均无)' % (d.year, d.timetuple().tm_yday))
        return tasks, missing

    def _igs_whu(self, ck, d1, d2, pending, nav_pending, tasks, sta_disp):
        api = self.whu(ck)
        if pending:
            sta4s = sorted({s for s, _ in pending})
            self.log('WHU 查询观测文件: %d 站 %s ~ %s ...' % (len(sta4s), d1, d2))
            rows = api.obs(sta4s, d1, d2)
            best = {}                                # (sta4, date) -> row
            for r in rows:
                try:
                    d = dt.date(int(r['year']), 1, 1) + dt.timedelta(int(r['day']) - 1)
                except Exception:
                    continue
                key = (str(r.get('site', ''))[:4].lower(), d)
                if key not in pending:
                    continue
                cur = best.get(key)
                if cur is None or (is_r3_obs(r['filename']) and not is_r3_obs(cur['filename'])):
                    best[key] = r
            for (sta4, d), row in sorted(best.items(), key=lambda kv: (kv[0][1], kv[0][0])):
                fname = row['filename']
                yyyy, ddd = str(d.year), '%03d' % d.timetuple().tm_yday
                rel = 'rinex/obs/%s/%s/%s' % (yyyy, ddd, fname)
                tasks.append(Task([api.url_of(row)],
                                  os.path.join(self.root, 'rinex', 'obs', yyyy, ddd, fname),
                                  rel, '%s %s/%s %s' % (sta_disp.get(sta4, sta4), yyyy, ddd, fname)))
                pending.discard((sta4, d))
            self.log('WHU 观测命中 %d / 待找 %d' % (len(best), len(pending)))
        if nav_pending:
            rows = api.nav(d1, d2)
            best = {}                                # date -> row
            for r in rows:
                try:
                    d = dt.date(int(r['year']), 1, 1) + dt.timedelta(int(r['day']) - 1)
                except Exception:
                    continue
                if d not in nav_pending:
                    continue
                fn = r['filename'].upper()
                pri = 0 if fn.startswith('BRDC00IGS') else (1 if fn.startswith('BRDM') else
                        (2 if fn.endswith('N.GZ') or fn.endswith('N.Z') else 3))
                cur = best.get(d)
                if cur is None or pri < cur[0]:
                    best[d] = (pri, r)
            for d, (pri, row) in sorted(best.items()):
                fname = row['filename']
                yyyy = str(d.year)
                rel = 'rinex/nav/%s/%s' % (yyyy, fname)
                tasks.append(Task([api.url_of(row)],
                                  os.path.join(self.root, 'rinex', 'nav', yyyy, fname),
                                  rel, 'brdc %s/%03d %s' % (yyyy, d.timetuple().tm_yday, fname)))
                nav_pending.discard(d)
            self.log('WHU 广播星历命中 %d / 待找 %d' % (len(best), len(nav_pending)))

    def _igs_dir(self, ck, cks, dates, pending, nav_pending, tasks):
        centers = self.src.centers()

        def one_day(date):
            ts, ms = [], []
            ph = placeholders(date)
            yyyy, ddd, yy = ph['YYYY'], ph['DDD'], ph['YY']
            if any(d == date for _, d in pending):
                tpl = centers.get(ck, {}).get('obs', '')
                url = fmt_url(tpl, ph)
                if url:
                    names = self.http.listing(url)
                    if names:
                        for sta4, d in sorted(list(pending)):
                            if d != date:
                                continue
                            fname = self._find_obs_in_listing(names, sta4)
                            if not fname:
                                continue
                            urls = []
                            for k in cks:
                                if self.src.centers().get(k, {}).get('kind') == 'dir':
                                    u = fmt_url(self.src.centers()[k].get('obs', ''), ph)
                                    if u:
                                        urls.append(u + fname)
                            if not urls:
                                urls = [url + fname]
                            rel = 'rinex/obs/%s/%s/%s' % (yyyy, ddd, fname)
                            ts.append((Task(urls, os.path.join(self.root, 'rinex', 'obs',
                                                               yyyy, ddd, fname),
                                            rel, '%s %s/%s %s' % (sta4, yyyy, ddd, fname)),
                                       (sta4, date)))
            if date in nav_pending:
                fname = None
                tpl = centers.get(ck, {}).get('nav', '')
                url = fmt_url(tpl, ph)
                if url:
                    names = self.http.listing(url)
                    for n in names:
                        nu = n.upper()
                        if nu.startswith(('BRDC00IGS', 'BRDM00DLR')) and ('%s%s' % (yyyy, ddd)) in nu:
                            fname = n
                            break
                    if not fname:
                        r2name = ('brdc%s0.%sn' % (ddd, yy)).lower()
                        for n in names:
                            if re.match(r'^brdc\d{3}0\.\d{2}n(\.(z|gz))?$', n, re.I) and \
                                    n.lower().startswith(r2name):
                                fname = n
                                break
                    if fname:
                        urls = [url + fname]
                        rel = 'rinex/nav/%s/%s' % (yyyy, fname)
                        ts.append((Task(urls, os.path.join(self.root, 'rinex', 'nav', yyyy, fname),
                                        rel, 'brdc %s/%s %s' % (yyyy, ddd, fname)), date))
            return ts, ms

        def fn(date):
            if self._stopped():
                return ([], [])
            return one_day(date)

        day_results = self._parallel_days_dir(dates, fn)
        for item in day_results:
            for t, key in item:
                tasks.append(t)
                if isinstance(key, tuple):
                    pending.discard(key)
                else:
                    nav_pending.discard(key)

    def _parallel_days_dir(self, dates, fn):
        results = [None] * len(dates)
        nwork = max(1, min(4, int(self.cfg.data.get('threads', 4))))
        with ThreadPoolExecutor(max_workers=nwork) as ex:
            futs = {ex.submit(fn, d): i for i, d in enumerate(dates)}
            for fut, i in futs.items():
                try:
                    results[i] = fut.result()
                except Exception:
                    results[i] = ([], [])
        return [r[0] for r in results if r]

    # ================= 模块2: 分析中心产品（fin/rap/ult） =================
    def _match_long(self, names, acid, series, mgex, ptypes, yyyy, ddd, hour=None):
        """长命名匹配。返回 {ptype: fname}。hour=None 表示非超快速。"""
        pre = '%s0%s_%s%s%s' % (acid.upper(), LONG_PRES[(series, mgex)], yyyy, ddd,
                                (hour + '00') if hour else '')
        out = {}
        for pt in ptypes:
            hits = [n for n in names if n.startswith(pre)
                    and any(k in n.upper() for k in LONG_KEYS[pt])]
            if hits:
                if pt == 'clk':                       # 优先 30s 钟差
                    h30 = [n for n in hits if '_30S_CLK' in n.upper()]
                    if h30:
                        hits = h30
                out[pt] = sorted(hits)[0]
        return out

    def _match_legacy(self, names, acid, series, ptypes, W, dow, hour=None):
        """短命名匹配（2022-11 前）。快速/超快速只有 IGS(igr/igu) 有短名。"""
        out = {}
        if series == 'rap' and acid != 'igs' or series == 'ult' and acid != 'igs':
            return out
        if series == 'fin':
            pre = '%s%d%d' % (acid, W, dow)
            tail = ''
        elif series == 'rap':
            pre = 'igr%d%d' % (W, dow)
            tail = ''
        else:
            pre = 'igu%d%d_%s' % (W, dow, hour or '00')
            tail = ''
        for pt in ptypes:
            for n in names:
                nl = n.lower()
                if not nl.startswith(pre):
                    continue
                if any(nl.endswith(e) or nl.endswith(e + '.z') or nl.endswith(e + '.gz')
                       for e in LEGACY_EXT[pt]):
                    out[pt] = n
                    break
        return out

    def _prod_dest(self, acid, series, yyyy, ddd, fname):
        rel = 'product/%s/%s/%s/%s/%s' % (acid, SERIES_DIR[series], yyyy, ddd, fname)
        return rel, os.path.join(self.root, 'product', acid, SERIES_DIR[series],
                                 yyyy, ddd, fname)

    def build_products(self, d1, d2, sel, center):
        """sel: {(acid, series): [ptypes]}；center: '自动' / 库名。
        按库顺序逐日回退：每天每产品先在首选库找，找不到再试下一库。"""
        cks = self._cks(center)
        ac_defs = {a['id']: a for a in self.src.analysis_centers()}
        dates = list(iter_dates(d1, d2))

        # 预取网页通道数据（一次查询覆盖整段日期）
        whu_map = {}          # ck -> {(acid,series,date,pt): (pri, fname, row)}
        aiub_names = {}       # (sub_tpl, year) -> names | None
        for ck in cks:
            kind = self.src.centers().get(ck, {}).get('kind', 'dir')
            if kind == 'whuweb':
                whu_map[ck] = self._prod_whu_fetch(ck, d1, d2, sel, ac_defs)
            elif kind == 'aiubweb':
                self._prod_aiub_prefetch(ck, dates, sel, ac_defs, aiub_names)

        def one_day(date):
            ts, ms = [], []
            ph = placeholders(date)
            yyyy, ddd = ph['YYYY'], ph['DDD']
            W, dow = int(ph['GPSW']), int(ph['GPSD'])
            for (acid, series), ptypes in sorted(sel.items()):
                if self._stopped():
                    break
                ac = ac_defs.get(acid, {})
                mgex = bool(ac.get('mgex'))
                if mgex and date.year < 2014:
                    for pt in ptypes:
                        ms.append('%s/%s %s/%s %s(MGEX 2014年起)' % (acid, SERIES_DIR[series],
                                                                  yyyy, ddd, pt))
                    continue
                kind_dir = 'mgex' if mgex else 'prod'
                hours = ULT_HOURS if series == 'ult' else [None]
                for hour in hours:
                    for pt in ptypes:
                        hit = None            # (urls, fname)
                        for ck in cks:
                            kind = self.src.centers().get(ck, {}).get('kind', 'dir')
                            if kind == 'whuweb':
                                cand = whu_map.get(ck, {}).get(
                                    (acid, series, date, hour if series == 'ult' else None, pt))
                                if cand:
                                    pri, fname, row = cand
                                    hit = ([self.whu(ck).url_of(row)], fname)
                                    break
                            elif kind == 'aiubweb':
                                if acid not in ('cod', 'com'):
                                    continue
                                sub_tpl = 'CODE_MGEX/CODE/{YYYY}' if mgex else 'CODE/{YYYY}'
                                names = aiub_names.get((sub_tpl, date.year))
                                if not names:
                                    continue
                                found = self._match_long(names, acid, series, mgex, [pt],
                                                         yyyy, ddd, hour)
                                if pt in found:
                                    sub = sub_tpl.replace('{YYYY}', str(date.year))
                                    hit = ([self.aiub(ck).file_url(sub, found[pt])], found[pt])
                                    break
                            else:
                                url = fmt_url(self.src.centers()[ck].get(kind_dir, ''), ph)
                                if not url:
                                    continue
                                names = self.http.listing(url)
                                if not names:
                                    continue
                                found = self._match_long(names, acid, series, mgex, [pt],
                                                         yyyy, ddd, hour)
                                if pt not in found:
                                    found = self._match_legacy(names, acid, series, [pt],
                                                               W, dow, hour)
                                if pt in found:
                                    urls = [url + found[pt]]
                                    for k in cks:      # 其他目录库作为回退地址
                                        if k == ck or self.src.centers().get(k, {}).get('kind') != 'dir':
                                            continue
                                        u2 = fmt_url(self.src.centers()[k].get(kind_dir, ''), ph)
                                        if u2:
                                            urls.append(u2 + found[pt])
                                    hit = (urls, found[pt])
                                    break
                        if hit:
                            urls, fname = hit
                            rel, dest = self._prod_dest(acid, series, yyyy, ddd, fname)
                            ts.append(Task(urls, dest, rel, '%s/%s %s/%s %s' % (
                                acid, SERIES_DIR[series], yyyy, ddd, fname)))
                        else:
                            ms.append('%s/%s %s/%s %s(各库均无)' % (acid, SERIES_DIR[series],
                                                                  yyyy, ddd, pt))
            return ts, ms

        dates_list = dates
        results = [None] * len(dates_list)
        nwork = max(1, min(8, int(self.cfg.data.get('threads', 4)) * 2))
        with ThreadPoolExecutor(max_workers=nwork) as ex:
            futs = {ex.submit(one_day, d): i for i, d in enumerate(dates_list)}
            for fut, i in futs.items():
                try:
                    results[i] = fut.result()
                except Exception as e:
                    results[i] = ([], ['生成任务出错: %s' % str(e)[:80]])
        tasks, missing = [], []
        for r in results:
            if r:
                tasks += r[0]
                missing += r[1]
        return tasks, missing

    def _prod_whu_fetch(self, ck, d1, d2, sel, ac_defs):
        """WHU 通道：一次查询返回 {(acid,series,date,pt): (pri, fname, row)}"""
        api = self.whu(ck)
        prefixes = sorted({a.upper() for (a, s), ps in sel.items() if ps})
        rows = []
        # GPS 周跨年归属：1月上旬的数据挂在'前一年'的最后一周，
        # 查询起点前扩 7 天兜底（多余日期由下游 d1<=d<=d2 过滤剔除）
        d1x = (dt.date(*[int(x) for x in d1.split('-')]) - dt.timedelta(7)).isoformat()
        for pre in prefixes:
            self.log('WHU 查询产品: %s %s ~ %s ...' % (pre, d1, d2))
            rows += api.products(pre, d1x, d2)
        self.log('WHU 产品记录 %d 条' % len(rows))
        if not rows:
            self.log('提示: WHU 该时段无产品数据（元旦/假期前后常有空缺），相关任务会自动回退其他库')
        cands = {}
        for r in rows:
            fn = r['filename']
            m = RE_FN_DATE.search(fn)
            if not m:
                continue
            yyyy, ddd, hour = m.group(1), m.group(2), m.group(3)
            try:
                d = dt.date(int(yyyy), 1, 1) + dt.timedelta(int(ddd) - 1)
            except ValueError:
                continue
            if not (d1 <= d.isoformat() <= d2):
                continue
            for (acid, series), pts in sel.items():
                ac = ac_defs.get(acid, {})
                pre = '%s0%s_' % (acid.upper(), LONG_PRES[(series, bool(ac.get('mgex')))])
                if not fn.startswith(pre):
                    continue
                if series == 'ult' and hour not in ULT_HOURS:
                    continue
                for pt in pts:
                    if any(k in fn.upper() for k in LONG_KEYS[pt]):
                        key = (acid, series, d, hour if series == 'ult' else None, pt)
                        pri = 0 if (pt == 'clk' and '_30S_CLK' in fn.upper()) else 1
                        cur = cands.get(key)
                        if cur is None or (pri, fn) < (cur[0], cur[1]):
                            cands[key] = (pri, fn, r)
        return cands

    def _prod_aiub_prefetch(self, ck, dates, sel, ac_defs, store):
        """AIUB 通道：预取相关年目录到 store[(sub_tpl, year)]"""
        api = self.aiub(ck)
        need = set()
        for (acid, series), pts in sel.items():
            if acid not in ('cod', 'com'):
                continue
            mgex = bool(ac_defs.get(acid, {}).get('mgex'))
            sub_tpl = 'CODE_MGEX/CODE/{YYYY}' if mgex else 'CODE/{YYYY}'
            for d in dates:
                if mgex and d.year < 2014:
                    continue
                need.add((sub_tpl, d.year))
        for sub_tpl, y in sorted(need):
            if (sub_tpl, y) in store:
                continue
            sub = sub_tpl.replace('{YYYY}', str(y))
            self.log('AIUB 读取目录: %s ...' % sub)
            store[(sub_tpl, y)] = api.listing(sub) or []

    # ================= 模块2b: 电离层 IONEX（目录型库） =================
    def build_ionex(self, d1, d2, ion_ids, center):
        cks = [c for c in self._cks(center)
               if self.src.centers().get(c, {}).get('kind') == 'dir']
        centers = self.src.centers()

        def one_day(date):
            tasks, missing = [], []
            ph = placeholders(date)
            yyyy, ddd, yy = ph['YYYY'], ph['DDD'], ph['YY']
            urls_by_ck, names_by_ck = {}, {}
            for ck in cks:
                u = fmt_url(centers.get(ck, {}).get('ion', ''), ph)
                if not u:
                    continue
                urls_by_ck[ck] = u
                names_by_ck[ck] = self.http.listing(u)
            for ion_id in ion_ids:
                fname = None
                for ck in cks:
                    for n in names_by_ck.get(ck, []):
                        nu = n.upper()
                        if nu.startswith(ion_id[:3].upper() + '0OPS') and 'GIM' in nu and \
                                ('%s%s' % (yyyy, ddd)) in nu:
                            fname = n
                            break
                    if not fname:
                        for n in names_by_ck.get(ck, []):
                            if re.match(r'^%s%s0\.%si(\.(z|gz))?$' % (ion_id[:4], ddd, yy), n, re.I):
                                fname = n
                                break
                    if fname:
                        break
                if not fname:
                    missing.append('%s %s/%s 电离层(各库均无)' % (ion_id, yyyy, ddd))
                    continue
                urls = [urls_by_ck[ck] + fname for ck in cks if ck in urls_by_ck]
                rel = 'product/%s/final/%s/%s/%s' % (ion_id[:3], yyyy, ddd, fname)
                dest = os.path.join(self.root, 'product', ion_id[:3], 'final', yyyy, ddd, fname)
                tasks.append(Task(urls, dest, rel, '%s %s/%s %s' % (ion_id, yyyy, ddd, fname)))
            return tasks, missing

        return self._parallel_days(d1, d2, one_day)

    # ================= 模块2c: CODE/AIUB 专属产品 =================
    def build_aiub(self, d1, d2, items):
        """items: ['gim','ion','bia','dcb']。存 product/cod/final/yyyy[/ddd]"""
        ck = 'CODE(AIUB)'
        if ck not in self.src.centers():
            return [], ['AIUB 存储库不存在']
        api = self.aiub(ck)
        tasks, missing = [], []
        names_cache = {}

        def year_names(y):
            if y not in names_cache:
                self.log('AIUB 读取目录: CODE/%d ...' % y)
                names_cache[y] = api.listing('CODE/%d' % y)
            return names_cache[y]

        daily_items = [i for i in items if i != 'dcb']

        def one_day(date):
            ts, ms = [], []
            if not daily_items:
                return ts, ms
            yyyy, ddd, yy = str(date.year), '%03d' % date.timetuple().tm_yday, str(date.year)[2:]
            names = year_names(date.year)
            if names is None:
                ms.append('AIUB %s (目录不可达)' % yyyy)
                return ts, ms
            for it in daily_items:
                fname = None
                if it == 'gim':
                    cands = [n for n in names if re.match(r'^CGIM%s0\.%sN\.(Z|gz)$' % (ddd, yy), n, re.I)]
                    if not cands:
                        cands = [n for n in names if 'GIM.INX' in n.upper() and ('%s%s' % (yyyy, ddd)) in n]
                    fname = sorted(cands)[0] if cands else None
                elif it == 'ion':
                    cands = [n for n in names if re.match(r'^COD%s%s\.ION(\.(Z|gz))?$' % (yy, ddd), n, re.I)]
                    if not cands:
                        cands = [n for n in names if 'GIM.ION' in n.upper() and ('%s%s' % (yyyy, ddd)) in n]
                    fname = sorted(cands)[0] if cands else None
                elif it == 'bia':
                    cands = [n for n in names if re.match(r'^COD%s%s\.BIA(\.(Z|gz))?$' % (yy, ddd), n, re.I)]
                    if not cands:
                        cands = [n for n in names if '_OSB.BIA' in n.upper() and ('%s%s' % (yyyy, ddd)) in n
                                 and 'MGX' not in n.upper()]
                    fname = sorted(cands)[0] if cands else None
                if not fname:
                    ms.append('AIUB %s %s/%s (未找到)' % (it.upper(), yyyy, ddd))
                    continue
                rel = 'product/cod/final/%s/%s/%s' % (yyyy, ddd, fname)
                dest = os.path.join(self.root, 'product', 'cod', 'final', yyyy, ddd, fname)
                ts.append(Task([api.file_url('CODE/%d' % date.year, fname)], dest, rel,
                               'AIUB %s %s/%s %s' % (it.upper(), yyyy, ddd, fname)))
            return ts, ms

        if daily_items:
            t, m = self._parallel_days(d1, d2, one_day)
            tasks += t
            missing += m
        if 'dcb' in items:
            months = sorted({(d.year, d.month) for d in iter_dates(d1, d2)})
            for (y, m) in months:
                names = year_names(y)
                if names is None:
                    missing.append('CODE DCB %d (目录不可达)' % y)
                    continue
                yy = str(y)[2:]
                for kind in ('P1C1', 'P1P2'):
                    pat = re.compile(r'^%s%s%02d\.(DCB|dcb)(\.(Z|gz))?$' % (kind, yy, m), re.I)
                    fname = next((n for n in names if pat.match(n)), None)
                    if not fname:
                        missing.append('CODE DCB %s %d-%02d (未找到)' % (kind, y, m))
                        continue
                    rel = 'product/cod/final/%d/%s' % (y, fname)
                    dest = os.path.join(self.root, 'product', 'cod', 'final', str(y), fname)
                    tasks.append(Task([api.file_url('CODE/%d' % y, fname)], dest, rel,
                                      'CODE DCB %d-%02d %s' % (y, m, fname)))
        return tasks, missing

    # ================= 模块3: hfile =================
    def build_hfile(self, d1, d2, src, prefix):
        tasks, missing = [], []
        hid = src['id']
        urls_tpl = src.get('urls', [])
        pre = (prefix or '').strip().lower()
        if src.get('by') == 'year':
            for y in sorted({d.year for d in iter_dates(d1, d2)}):
                ph = placeholders(dt.date(y, 6, 1))
                names, base = [], None
                for tpl in urls_tpl:
                    u = fmt_url(tpl, ph)
                    if not u:
                        continue
                    names = self.http.listing(u)
                    if names:
                        base = u
                        break
                if not base:
                    missing.append('%s hfile %d (目录不可达)' % (hid.upper(), y))
                    continue
                got = False
                for n in names:
                    if not n.lower().startswith('h'):
                        continue
                    if pre and pre not in n.lower():
                        continue
                    rel = 'hfile/%s/%d/%s' % (hid, y, n)
                    tasks.append(Task([base + n], os.path.join(self.root, 'hfile', hid, str(y), n),
                                      rel, '%s hfile %d %s' % (hid.upper(), y, n)))
                    got = True
                if not got:
                    missing.append('%s hfile %d (无匹配前缀文件)' % (hid.upper(), y))
        else:
            def one_day(date):
                ts, ms = [], []
                ph = placeholders(date)
                yyyy, ddd = ph['YYYY'], ph['DDD']
                names, base = [], None
                for tpl in urls_tpl:
                    u = fmt_url(tpl, ph)
                    if not u:
                        continue
                    names = self.http.listing(u)
                    if names:
                        base = u
                        break
                if not base:
                    ms.append('%s hfile %s/%s (目录不可达)' % (hid.upper(), yyyy, ddd))
                    return ts, ms
                got = False
                for n in names:
                    if not n.lower().startswith('h'):
                        continue
                    if pre and pre not in n.lower():
                        continue
                    rel = 'hfile/%s/%s/%s' % (hid, yyyy, n)
                    ts.append(Task([base + n], os.path.join(self.root, 'hfile', hid, yyyy, n),
                                   rel, '%s hfile %s/%s %s' % (hid.upper(), yyyy, ddd, n)))
                    got = True
                if not got:
                    ms.append('%s hfile %s/%s (无匹配前缀文件)' % (hid.upper(), yyyy, ddd))
                return ts, ms
            t, m = self._parallel_days(d1, d2, one_day)
            tasks += t
            missing += m
        return tasks, missing

    # ================= 模块4: 区域网 =================
    def build_regional(self, d1, d2, src, stations):
        templates = src.get('templates', [])
        rid = src['id']

        def one_day(date):
            ts, ms = [], []
            ph = placeholders(date)
            yyyy, ddd = ph['YYYY'], ph['DDD']
            day_lists = {}

            def day_listing(tpl):
                if tpl not in day_lists:
                    u = fmt_url(tpl, ph)
                    day_lists[tpl] = (u, self.http.listing(u)) if u else (None, [])
                return day_lists[tpl]

            for sta in stations:
                phs = placeholders(date, sta)
                fname, base = None, None
                for tpl in templates:
                    if tpl_needs_sta(tpl):
                        u = fmt_url(tpl, phs)
                        if not u:
                            continue
                        names = self.http.listing(u)
                        for n in names:                     # 有3先下3
                            if is_r3_obs(n):
                                fname, base = n, u
                                break
                        if not fname:
                            for n in names:
                                if RE_R2_OBS.match(n):
                                    fname, base = n, u
                                    break
                    else:
                        u, names = day_listing(tpl)
                        fname0 = self._find_obs_in_listing(names, sta)
                        if fname0:
                            fname, base = fname0, _dl_base(u)
                    if fname:
                        break
                if not fname:
                    ms.append('%s %s %s/%s (无观测文件)' % (rid.upper(), sta, yyyy, ddd))
                    continue
                rel = 'rinex/obs/%s/%s/%s' % (yyyy, ddd, fname)
                ts.append(Task([base + fname], os.path.join(self.root, 'rinex', 'obs', yyyy, ddd, fname),
                               rel, '%s %s %s/%s %s' % (rid.upper(), sta, yyyy, ddd, fname)))
            return ts, ms

        return self._parallel_days(d1, d2, one_day)


# ----------------------------------------------------------------------
# 图形界面
# ----------------------------------------------------------------------

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

CHK_ON = '☑'
CHK_OFF = '☐'
CHK_PART = '▣'

IGS_DEFAULT_STATIONS = ['bjfs', 'bjnm', 'chan', 'kunm', 'lhaz', 'shao', 'urum',
                        'wuhn', 'xian', 'guao', 'wuh2', 'algo', 'brux', 'kour',
                        'usud', 'yarr', 'chl1', 'hkws']


class StationTable(ttk.Frame):
    """测站树：洲/分组=父节点（可折叠），测站=子节点。支持 4 位或 9 位站名。"""

    def __init__(self, master, height=8, on_map=None):
        super().__init__(master)
        self.tree = ttk.Treeview(self, columns=('sel',), show='tree headings',
                                 height=height, selectmode='extended')
        self.tree.heading('#0', text=tr('col_station'))
        self.tree.heading('sel', text=tr('col_dl'))
        self.tree.column('#0', width=240)
        self.tree.column('sel', width=40, anchor='center', stretch=False)
        sb = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='left', fill='y')
        self.tree.tag_configure('header', background='#e8eef7',
                                font=('TkDefaultFont', 9, 'bold'))
        self.tree.bind('<Button-1>', self._toggle)
        btns = ttk.Frame(self)
        btns.pack(side='left', fill='y', padx=4)
        items = [(tr('btn_add'), self.add), (tr('btn_del'), self.remove),
                 (tr('btn_selall'), self.select_all), (tr('btn_selnone'), self.select_none),
                 (tr('btn_import'), self.import_txt), (tr('btn_paste'), self.paste_import),
                 (tr('btn_clear'), self.clear)]
        if on_map:
            items.insert(4, (tr('btn_map'), on_map))
        for txt, cmd in items:
            ttk.Button(btns, text=txt, width=9, command=cmd).pack(pady=1)

    # ---------- 行工具 ----------
    def _station_rows(self):
        """所有测站行 iid（含父节点的子行 + 顶层非分组行）"""
        out = []
        for iid in self.tree.get_children():
            if self.tree.get_children(iid):          # 分组父节点
                out.extend(self.tree.get_children(iid))
            else:
                out.append(iid)
        return out

    def _is_group(self, iid):
        return bool(self.tree.get_children(iid)) or \
                self.tree.item(iid, 'text').startswith('#')

    def _toggle(self, ev):
        iid = self.tree.identify_row(ev.y)
        if not iid or self.tree.identify_column(ev.x) != '#1':
            return
        if self._is_group(iid):                      # 父节点：级联切换全部子站
            kids = self.tree.get_children(iid)
            if not kids:
                return 'break'
            any_off = any(self.tree.set(k, 'sel') != CHK_ON for k in kids)
            for k in kids:
                self.tree.set(k, 'sel', CHK_ON if any_off else CHK_OFF)
        else:
            v = self.tree.set(iid, 'sel')
            self.tree.set(iid, 'sel', CHK_OFF if v == CHK_ON else CHK_ON)
        self._refresh_groups()
        return 'break'

    def _refresh_groups(self):
        """按子站状态刷新洲分组的三态框：全选☑ / 全不选☐ / 部分▣"""
        for gid in self.tree.get_children():
            kids = self.tree.get_children(gid)
            if not kids:
                continue
            on = sum(1 for k in kids if self.tree.set(k, 'sel') == CHK_ON)
            st = CHK_ON if on == len(kids) else (CHK_OFF if on == 0 else CHK_PART)
            self.tree.set(gid, 'sel', st)

    def _insert_station(self, name, checked=False, parent=''):
        self.tree.insert(parent, 'end', text=name.strip(),
                         values=(CHK_ON if checked else CHK_OFF,))

    # ---------- 按钮动作 ----------
    def add(self):
        s = simpledialog.askstring(tr('btn_add'), tr('col_station') + ' (a,b,c):', parent=self)
        if not s:
            return
        for name in re.split(r'[,\s;；，]+', s.strip()):
            if name:
                self._insert_station(name)

    def remove(self):
        for iid in self.tree.selection():
            self.tree.delete(iid)

    def select_all(self):
        for iid in self._station_rows():
            self.tree.set(iid, 'sel', CHK_ON)
        self._refresh_groups()

    def select_none(self):
        for iid in self._station_rows():
            self.tree.set(iid, 'sel', CHK_OFF)
        self._refresh_groups()

    def clear(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)

    def import_txt(self):
        p = filedialog.askopenfilename(filetypes=[('txt', '*.txt'), ('all', '*.*')])
        if not p:
            return
        with open(p, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                for name in re.split(r'[,\s;；，]+', line.strip()):
                    if name:
                        self._insert_station(name)

    def paste_import(self):
        """从剪贴板导入站名并直接勾选（配合地图选站使用）。"""
        try:
            text = self.winfo_toplevel().clipboard_get()
        except Exception:
            messagebox.showinfo(tr('msg_tip'), 'clipboard empty')
            return
        names = [n for n in re.split(r'[,\s;；，]+', text.strip()) if n]
        if not names:
            return
        rows = {}
        for iid in self._station_rows():
            rows[self.tree.item(iid, 'text')[:4].lower()] = iid
        n_new = n_mark = 0
        for name in names:
            key = name.strip()[:4].lower()
            if key in rows:
                self.tree.set(rows[key], 'sel', CHK_ON)
                n_mark += 1
            else:
                self._insert_station(name, checked=True)
                n_new += 1
        self._refresh_groups()
        messagebox.showinfo(tr('msg_tip'), '%d checked, %d new' % (n_mark, n_new))

    def set_stations(self, stations):
        self.clear()
        for s in stations:
            self._insert_station(s)

    def get_selected(self):
        out = []
        for iid in self._station_rows():
            if self.tree.set(iid, 'sel') == CHK_ON:
                out.append(re.sub(r'\s*\([A-Z]{3}\)$', '',
                                  self.tree.item(iid, 'text')).strip())
        return out

    def set_checked(self, keys):
        keys = {k.lower() for k in keys}
        for iid in self._station_rows():
            hit = self.tree.item(iid, 'text')[:4].lower() in keys
            self.tree.set(iid, 'sel', CHK_ON if hit else CHK_OFF)
        self._refresh_groups()

    def set_grouped(self, path):
        """按洲分块加载（可折叠；中国站在亚洲块最前，默认只展开亚洲）"""
        groups = load_stations_grouped(path)
        if not groups:
            return False
        self.clear()
        for cont, items in groups:
            pid = self.tree.insert('', 'end', text='# ' + tr('cont_' + cont),
                                   values=(CHK_OFF,), tags=('header',),
                                   open=(cont == 'asia'))
            for line, cc in items:
                self._insert_station(line, parent=pid)
        return True


class DateRange(ttk.Frame):
    """全局日期栏：所有页签联动共用。"""

    def __init__(self, master):
        super().__init__(master)
        yest = dt.date.today() - dt.timedelta(days=2)
        ttk.Label(self, text=tr('start_date')).pack(side='left')
        self.d1 = ttk.Entry(self, width=12)
        self.d1.insert(0, yest.strftime('%Y-%m-%d'))
        self.d1.pack(side='left', padx=4)
        ttk.Label(self, text=tr('end_date')).pack(side='left')
        self.d2 = ttk.Entry(self, width=12)
        self.d2.insert(0, yest.strftime('%Y-%m-%d'))
        self.d2.pack(side='left', padx=4)
        for key, days in (('yesterday', 1), ('last7', 7), ('last30', 30)):
            ttk.Button(self, text=tr(key), width=8,
                       command=lambda n=days: self._quick(n)).pack(side='left', padx=1)
        ttk.Label(self, text='(YYYY-MM-DD)', foreground='gray').pack(side='left', padx=(4, 0))

    def _quick(self, days):
        e = dt.date.today() - dt.timedelta(days=1)
        s = e - dt.timedelta(days=days - 1)
        for w, v in ((self.d1, s), (self.d2, e)):
            w.delete(0, 'end')
            w.insert(0, v.strftime('%Y-%m-%d'))

    def get(self):
        s, e = self.d1.get().strip(), self.d2.get().strip()
        dt.date(*[int(x) for x in s.split('-')])
        dt.date(*[int(x) for x in e.split('-')])
        return s, e


class FormDialog(tk.Toplevel):
    """通用编辑弹窗。fields: [(key, label, kind)]；kind: entry/text/check/combo:a,b"""

    def __init__(self, parent, title, fields, values=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()
        self.result = None
        self._vars = {}
        values = values or {}
        for i, (key, label, kind) in enumerate(fields):
            ttk.Label(self, text=label).grid(row=i, column=0, sticky='ne', padx=6, pady=3)
            if kind == 'text':
                w = tk.Text(self, width=64, height=5)
                w.insert('1.0', values.get(key, ''))
                w.grid(row=i, column=1, padx=6, pady=3, sticky='ew')
                self._vars[key] = ('text', w)
            elif kind == 'check':
                v = tk.BooleanVar(value=bool(values.get(key)))
                ttk.Checkbutton(self, variable=v).grid(row=i, column=1, sticky='w', padx=6)
                self._vars[key] = ('var', v)
            elif kind.startswith('combo:'):
                v = tk.StringVar(value=values.get(key, ''))
                ttk.Combobox(self, textvariable=v, state='readonly', width=20,
                             values=kind[6:].split(',')).grid(row=i, column=1, sticky='w', padx=6)
                self._vars[key] = ('var', v)
            else:
                e = ttk.Entry(self, width=68)
                e.insert(0, values.get(key, ''))
                e.grid(row=i, column=1, padx=6, pady=3, sticky='ew')
                self._vars[key] = ('entry', e)
        bf = ttk.Frame(self)
        bf.grid(row=len(fields), column=0, columnspan=2, pady=8)
        ttk.Button(bf, text=tr('btn_ok'), command=self._ok).pack(side='left', padx=8)
        ttk.Button(bf, text=tr('btn_cancel'), command=self.destroy).pack(side='left')
        self.columnconfigure(1, weight=1)
        self.update_idletasks()
        self.geometry('+%d+%d' % (parent.winfo_rootx() + 60, parent.winfo_rooty() + 60))
        self.wait_window()

    def _ok(self):
        self.result = {}
        for key, (kind, w) in self._vars.items():
            if kind == 'text':
                self.result[key] = w.get('1.0', 'end').strip()
            elif kind == 'var':
                self.result[key] = w.get()
            else:
                self.result[key] = w.get().strip()
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.cfg = Config()
        self.hist = History()
        self.src = Sources()
        self.http = Http(self.cfg, self.src)
        self.q = queue.Queue()
        self.worker = None
        self._active = {}
        self._build_ui()
        self._restore_ui()
        self.protocol('WM_DELETE_WINDOW', self._on_close)
        self.after(150, self._pump)

    def _build_ui(self):
        """构建（或语言切换后重建）整个界面"""
        for w in self.winfo_children():
            w.destroy()
        self.title(tr('app_title'))
        try:
            self.iconbitmap(_res_path('gnss.ico'))
        except Exception:
            pass
        self.geometry('1020x780')
        # 全局日期栏（所有页签联动）
        top = ttk.Frame(self)
        top.pack(fill='x', padx=6, pady=(6, 0))
        self.dates = DateRange(top)
        self.dates.pack(side='left')
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill='both', expand=True, padx=6, pady=6)
        self._tab_igs()
        self._tab_product()
        self._tab_hfile()
        self._tab_region()
        self._tab_sources()
        self._tab_settings()
        self._tab_about()
        self._bottom()
        self.nb.bind('<<NotebookTabChanged>>', self._on_tab_changed)

    # ---------------- IGS 观测页 ----------------
    def _tab_igs(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text=tr('tab_igs'))
        top = ttk.Frame(f)
        top.pack(fill='x', pady=4)
        self.igs_obs = tk.BooleanVar(value=False)
        self.igs_nav = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text=tr('obs_files'), variable=self.igs_obs).pack(side='left', padx=4)
        ttk.Checkbutton(top, text=tr('nav_brdc'), variable=self.igs_nav).pack(side='left')
        ttk.Label(top, text=tr('repo')).pack(side='left', padx=(14, 2))
        repos = [k for k, v in self.src.centers().items() if v.get('kind') != 'aiubweb']
        self.igs_center = ttk.Combobox(top, width=10, state='readonly',
                                       values=repos)
        if repos:
            self.igs_center.set(repos[0])
        self.igs_center.pack(side='left')
        ttk.Button(top, text=tr('set_speed'),
                   command=lambda: self._speed_test(
                       on_pick=lambda k: self.igs_center.set(k))).pack(side='left', padx=4)
        ttk.Label(top, text=tr('hint_igs'), foreground='gray').pack(side='left', padx=10)
        self.igs_table = StationTable(f, on_map=self._open_station_map)
        self.igs_table.pack(fill='both', expand=True, pady=4)
        if not self.igs_table.set_grouped(stations_txt_path()):
            self.igs_table.set_stations(IGS_DEFAULT_STATIONS)

    # ---------------- 产品页（存储库 -> 机构+系列 -> 产品） ----------------
    def _tab_product(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text=tr('tab_prod'))
        ph = ttk.Frame(f)
        ph.pack(fill='x')
        ttk.Label(ph, text=tr('hint_prod'), foreground='gray').pack(side='left', pady=2)
        ttk.Button(ph, text=tr('set_speed'),
                   command=lambda: self._speed_test(on_pick=self._prd_open_repo)).pack(side='right')
        self.prd_tree = ttk.Treeview(f, columns=('sel',), show='tree headings')
        self.prd_tree.heading('#0', text=tr('col_repo_prod'))
        self.prd_tree.heading('sel', text=tr('col_dl'))
        self.prd_tree.column('#0', width=460)
        self.prd_tree.column('sel', width=44, anchor='center', stretch=False)
        sb = ttk.Scrollbar(f, orient='vertical', command=self.prd_tree.yview)
        self.prd_tree.configure(yscrollcommand=sb.set)
        self.prd_tree.pack(fill='both', expand=True, side='left')
        sb.pack(side='left', fill='y')
        self.prd_tree.bind('<Button-1>', self._prd_toggle)
        self._build_product_tree()

    def _build_product_tree(self):
        self.prd_tree.delete(*self.prd_tree.get_children())
        self._prd_nodes = {}     # 叶子 iid -> ('prod', repo, acid, series, pt)
                                 #          ('ionex', repo, ionid) / ('aiub', itemid)
        acs = self.src.analysis_centers()
        ions = self.src.ionex()
        centers = self.src.centers()
        # 第一层：各存储库
        repos = [(k, k) for k, v in centers.items() if v.get('kind') != 'aiubweb']
        for i, (key, label) in enumerate(repos):
            kind = centers.get(key, {}).get('kind', '')
            addr = centers[key].get('api') or centers[key].get('prod', '')
            disp = '%s    %s' % (label, addr)
            pid = self.prd_tree.insert('', 'end', text=disp, values=(CHK_OFF,),
                                       open=(i == 0))
            for ac in acs:
                for series in SERIES_IDS:
                    pts = ac.get('series', {}).get(series)
                    if not pts:
                        continue
                    if kind == 'whuweb' and ac.get('mgex'):
                        # 武大网页库实测只索引 WUM 快速，MGEX 最终不显示
                        if not (ac['id'] == 'wum' and series == 'rap'):
                            continue
                    name = '%s %s' % (ac['name'], tr(series))
                    if ac.get('mgex'):
                        name += '   ' + tr('mgex_tail')
                    aid = self.prd_tree.insert(pid, 'end', text=name, values=(CHK_OFF,))
                    for pt in pts:
                        cid = self.prd_tree.insert(aid, 'end',
                                                   text=tr(PRODUCT_NAMES.get(pt, 'pt_erp')),
                                                   values=(CHK_OFF,))
                        self._prd_nodes[cid] = ('prod', key, ac['id'], series, pt)
            if kind != 'whuweb' and ions:               # 武大库无电离层
                inode = self.prd_tree.insert(pid, 'end', text=tr('pt_ionex'), values=(CHK_OFF,))
                for ion in ions:
                    cid = self.prd_tree.insert(inode, 'end',
                                               text='%s  %s' % (ion['id'], ion['name']),
                                               values=(CHK_OFF,))
                    self._prd_nodes[cid] = ('ionex', key, ion['id'])
        # CODE(AIUB) 库：CODE 产品 + AIUB 专属
        if 'CODE(AIUB)' in centers:
            c = centers['CODE(AIUB)']
            pid = self.prd_tree.insert('', 'end', text='CODE(AIUB)    %s' % c.get('prod', ''),
                                       values=(CHK_OFF,))
            for ac in acs:
                if ac['id'] not in ('cod', 'com'):
                    continue
                for series in SERIES_IDS:
                    pts = ac.get('series', {}).get(series)
                    if not pts:
                        continue
                    name = '%s %s' % (ac['name'], tr(series))
                    if ac.get('mgex'):
                        name += '   ' + tr('mgex_tail')
                    aid = self.prd_tree.insert(pid, 'end', text=name, values=(CHK_OFF,))
                    for pt in pts:
                        cid = self.prd_tree.insert(aid, 'end',
                                                   text=tr(PRODUCT_NAMES.get(pt, 'pt_erp')),
                                                   values=(CHK_OFF,))
                        self._prd_nodes[cid] = ('prod', 'CODE(AIUB)', ac['id'], series, pt)
            anode = self.prd_tree.insert(pid, 'end', text='AIUB', values=(CHK_OFF,))
            for it in self.src.aiub().get('items', []):
                cid = self.prd_tree.insert(anode, 'end', text=it['name'], values=(CHK_OFF,))
                self._prd_nodes[cid] = ('aiub', it['id'])

    def _prd_toggle(self, ev):
        iid = self.prd_tree.identify_row(ev.y)
        if not iid or self.prd_tree.identify_column(ev.x) != '#1':
            return
        if iid in self._prd_nodes:                       # 叶子：直接切换
            v = self.prd_tree.set(iid, 'sel')
            self.prd_tree.set(iid, 'sel', CHK_OFF if v == CHK_ON else CHK_ON)
        else:                                            # 父节点：级联切换全部叶子
            leaves = [d for d in self._prd_nodes if self._is_descendant(iid, d)]
            if not leaves:
                return 'break'
            any_off = any(self.prd_tree.set(d, 'sel') != CHK_ON for d in leaves)
            for d in leaves:
                self.prd_tree.set(d, 'sel', CHK_ON if any_off else CHK_OFF)
        self._prd_refresh()
        return 'break'

    def _prd_refresh(self):
        """按叶子状态刷新全部父节点的三态框：全选☑ / 全不选☐ / 部分▣"""
        parents = set()
        for leaf in self._prd_nodes:
            p = self.prd_tree.parent(leaf)
            while p:
                parents.add(p)
                p = self.prd_tree.parent(p)
        for p in parents:
            leaves = [d for d in self._prd_nodes if self._is_descendant(p, d)]
            if not leaves:
                continue
            on = sum(1 for d in leaves if self.prd_tree.set(d, 'sel') == CHK_ON)
            st = CHK_ON if on == len(leaves) else (CHK_OFF if on == 0 else CHK_PART)
            self.prd_tree.set(p, 'sel', st)

    def _is_descendant(self, pid, iid):
        while iid:
            if iid == pid:
                return True
            iid = self.prd_tree.parent(iid)
        return False

    # ---------------- hfile 页 ----------------
    def _tab_hfile(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text=tr('tab_hfile'))
        self.hf_body = ttk.Frame(f)
        self.hf_body.pack(fill='both', expand=True)
        self._build_hfile_body()

    def _build_hfile_body(self):
        for w in self.hf_body.winfo_children():
            w.destroy()
        self.hf_vars = {}
        for src in self.src.hfile():
            g = ttk.LabelFrame(self.hf_body,
                               text='%s (%s) -> hfile/%s/yyyy'
                                    % (src['name'], src.get('by', 'day'), src['id']))
            g.pack(fill='x', pady=4, padx=4)
            v = tk.BooleanVar(value=False)
            ttk.Checkbutton(g, variable=v).pack(side='left', padx=4)
            ttk.Label(g, text=tr('hf_net')).pack(side='left', padx=(12, 2))
            e = ttk.Entry(g, width=16)
            e.insert(0, src.get('prefix', ''))
            e.pack(side='left')
            ttk.Label(g, text=(src.get('urls') or [''])[0],
                      foreground='gray').pack(side='left', padx=12)
            self.hf_vars[src['id']] = (v, e)

    # ---------------- 区域网页 ----------------
    def _tab_region(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text=tr('tab_region'))
        self.rg_body = ttk.Frame(f)
        self.rg_body.pack(fill='both', expand=True)
        self._build_region_body()

    def _rg_snapshot(self):
        """收集当前区域网页状态（重建/恢复用），以界面为准、配置兜底"""
        ui = self.cfg.data.get('ui') or {}
        snap = {'enable': {k: bool(v) for k, v in (ui.get('rg_enable') or {}).items()},
                'checked': {k: list(v) for k, v in (ui.get('rg_stations') or {}).items()},
                'stations': {},
                'collapsed': dict(getattr(self, '_rg_collapsed', None)
                                  or ui.get('rg_collapsed') or {})}
        for rid, v in getattr(self, 'rg_enable', {}).items():
            snap['enable'][rid] = bool(v.get())
        for rid, tb in getattr(self, 'rg_tables', {}).items():
            snap['checked'][rid] = tb.get_selected()
            snap['stations'][rid] = [tb.tree.item(i, 'text') for i in tb._station_rows()]
        return snap

    def _build_region_body(self, from_src=False):
        """from_src=True 表示数据源刚被修改：站名以源定义为准（勾选按站名保留）。"""
        keep = self._rg_snapshot()
        for w in self.rg_body.winfo_children():
            w.destroy()
        self.rg_enable = {}
        self.rg_tables = {}
        self._rg_blocks = {}
        self._rg_collapsed = dict(keep['collapsed'])
        bar = ttk.Frame(self.rg_body)
        bar.pack(fill='x', pady=(2, 0))
        ttk.Button(bar, text=tr('btn_add_net'), command=self._rg_add).pack(side='left')
        cv = tk.Canvas(self.rg_body, highlightthickness=0)
        vsb = ttk.Scrollbar(self.rg_body, orient='vertical', command=cv.yview)
        inner = ttk.Frame(cv)
        win = cv.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: cv.configure(scrollregion=cv.bbox('all')))
        cv.bind('<Configure>', lambda e: cv.itemconfigure(win, width=e.width))
        cv.configure(yscrollcommand=vsb.set)
        cv.pack(side='left', fill='both', expand=True)
        vsb.pack(side='right', fill='y')
        first = True
        for src in self.src.regional():
            rid = src['id']
            block = ttk.Frame(inner)
            block.pack(fill='x', pady=2, padx=2)
            head = ttk.Frame(block)
            head.pack(fill='x')
            v = tk.BooleanVar(value=bool(keep['enable'].get(rid, False)))
            self.rg_enable[rid] = v
            ttk.Checkbutton(head, variable=v).pack(side='left')
            tog = ttk.Button(head, width=2,
                             command=lambda r=rid: self._rg_toggle_block(r))
            tog.pack(side='left')
            ttk.Label(head, text='%s -> rinex/obs/yyyy/ddd' % src['name'],
                      font=('TkDefaultFont', 9, 'bold')).pack(side='left', padx=4)
            if src.get('auth') == 'esdevice':
                ok = self._es_token_ok(rid)
                ttk.Button(head, text=tr('es_btn'), width=9,
                           command=lambda r=rid: self._es_login(r)
                           ).pack(side='left', padx=(10, 2))
                ttk.Label(head, text=tr('es_ok') if ok else tr('es_no'),
                          foreground=('#1a7f37' if ok else '#c0392b')
                          ).pack(side='left', padx=2)
            ttk.Button(head, text=tr('btn_selnone'), width=6,
                       command=lambda r=rid: self.rg_tables[r].select_none()
                       ).pack(side='right', padx=1)
            ttk.Button(head, text=tr('btn_selall'), width=6,
                       command=lambda r=rid: self.rg_tables[r].select_all()
                       ).pack(side='right', padx=1)
            body = ttk.Frame(block)
            tb = StationTable(body, height=10)
            tb.pack(fill='both', expand=True)
            stas = (src.get('stations', []) if from_src
                    else (keep['stations'].get(rid) or src.get('stations', [])))
            tb.set_stations(stas)
            if keep['checked'].get(rid):
                tb.set_checked(keep['checked'][rid])
            self.rg_tables[rid] = tb
            self._rg_blocks[rid] = (tog, body)
            col = self._rg_collapsed.get(rid)
            if col is None:
                col = not first                       # 默认只展开第一个网
                self._rg_collapsed[rid] = col
            tog.configure(text='\u25b8' if col else '\u25be')
            if not col:
                body.pack(fill='both', expand=True)
            first = False

    def _rg_toggle_block(self, rid):
        col = not self._rg_collapsed.get(rid, False)
        self._rg_collapsed[rid] = col
        tog, body = self._rg_blocks[rid]
        if col:
            body.forget()
            tog.configure(text='\u25b8')
        else:
            body.pack(fill='both', expand=True)
            tog.configure(text='\u25be')

    def _rg_add(self):
        r = FormDialog(self, tr('grp_region') + ' +', [
            ('id', 'id', 'entry'), ('name', 'name', 'entry'),
            ('templates', 'templates ({YYYY}/{DDD}/{SSSS})', 'text'),
            ('stations', 'stations', 'text'),
            ('user', tr('src_user'), 'entry'), ('pass', tr('src_pass'), 'entry')])
        if not (r.result and r.result.get('id')):
            return
        self.src.data.setdefault('regional', []).append({
            'id': r.result['id'], 'name': r.result['name'] or r.result['id'],
            'templates': [x.strip() for x in r.result['templates'].splitlines() if x.strip()],
            'stations': [x for x in re.split(r'[\s,;，；]+', r.result['stations']) if x],
            'user': r.result.get('user', '').strip(),
            'pass': enc(r.result.get('pass', '').strip())})
        self.src.save()
        self._after_sources_changed()

    def _es_token_ok(self, rid):
        for r in self.src.regional():
            if r.get('id') == rid:
                return bool(r.get('es_token'))
        return False

    def _es_login(self, rid):
        """EarthScope OAuth device flow：弹验证码 -> 浏览器确认 -> 后台轮询拿 token。"""
        try:
            d = _es_form_post('/oauth/device/code', {
                'client_id': ES_AUTH['client_id'],
                'audience': ES_AUTH['audience'],
                'scope': ES_AUTH['scope']})
        except Exception as e:
            messagebox.showerror(tr('msg_err'), 'EarthScope: %s' % e)
            return
        win = tk.Toplevel(self)
        win.title('EarthScope')
        win.transient(self)
        tk.Label(win, text=tr('es_lg_tip'), justify='left').pack(padx=14, pady=(14, 4))
        tk.Label(win, text=d.get('user_code', ''),
                 font=('TkDefaultFont', 16, 'bold')).pack()
        url = d.get('verification_uri_complete') or d.get('verification_uri', '')
        ttk.Button(win, text=tr('es_open'),
                   command=lambda: os.startfile(url)).pack(pady=4)
        stat = tk.Label(win, text=tr('es_wait'), foreground='gray')
        stat.pack(padx=14, pady=(4, 14))
        stop = {'v': False}

        def on_close():
            stop['v'] = True
            win.destroy()
        win.protocol('WM_DELETE_WINDOW', on_close)

        def poll():
            interval = int(d.get('interval', 5))
            deadline = time.time() + int(d.get('expires_in', 900))
            fail = None
            while not stop['v'] and time.time() < deadline:
                time.sleep(max(interval, 2))
                if stop['v']:
                    return
                try:
                    r = _es_form_post('/oauth/token', {
                        'grant_type': 'urn:ietf:params:oauth:grant-type:device_code',
                        'device_code': d['device_code'],
                        'client_id': ES_AUTH['client_id']})
                    entry = self.src.es_entry()
                    if entry is not None:
                        entry['es_token'] = enc(json.dumps({
                            'access': r['access_token'],
                            'refresh': r.get('refresh_token', ''),
                            'exp': time.time() + int(r.get('expires_in', 86400)) - 120}))
                        self.src.save()
                    self.http.reset()
                    self.q.put(('log', 'EarthScope 授权成功 / authorized'))
                    def ok_close():
                        stop['v'] = True
                        win.destroy()
                        self._build_region_body()
                    self.after(0, ok_close)
                    return
                except urllib.error.HTTPError as e:
                    try:
                        ej = json.loads(e.read().decode('utf-8', 'replace'))
                    except Exception:
                        ej = {}
                    err = ej.get('error', '')
                    if err == 'authorization_pending':
                        continue
                    if err == 'slow_down':
                        interval += 2
                        continue
                    fail = ej.get('error_description') or err or str(e)
                    break
                except Exception as e:
                    fail = str(e)
                    time.sleep(interval)
            if fail:
                self.q.put(('log', 'EarthScope 授权失败: %s' % fail))
            if not stop['v']:
                self.after(0, lambda: stat.configure(text=tr('es_timeout'),
                                                     foreground='#c0392b'))
        threading.Thread(target=poll, daemon=True).start()

    # ---------------- 数据源管理页 ----------------
    def _tab_sources(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text=tr('tab_sources'))
        tip = ttk.Label(f, foreground='gray', text=tr('src_tip'))
        tip.pack(anchor='w', pady=2)
        self.src_tree = ttk.Treeview(f, columns=('val',), show='tree headings')
        self.src_tree.heading('#0', text='')
        self.src_tree.heading('val', text='URL')
        self.src_tree.column('#0', width=200)
        self.src_tree.column('val', width=640)
        self.src_tree.pack(fill='both', expand=True, side='left', padx=(0, 2))
        sb = ttk.Scrollbar(f, orient='vertical', command=self.src_tree.yview)
        self.src_tree.configure(yscrollcommand=sb.set)
        sb.pack(side='left', fill='y')
        self.src_tree.bind('<Double-1>', lambda e: self._src_edit())
        btns = ttk.Frame(f)
        btns.pack(side='left', fill='y', padx=4)
        for txt, cmd in ((tr('btn_modify') if False else '修改', self._src_edit),
                         ('新增', self._src_add), ('删除', self._src_del),
                         ('恢复默认', self._src_reset), ('保存', self._src_save)):
            ttk.Button(btns, text=txt, width=10, command=cmd).pack(pady=2)
        self._src_btn_labels = True
        self._build_sources_tree()

    def _build_sources_tree(self):
        self.src_tree.delete(*self.src_tree.get_children())
        self._src_map = {}
        d = self.src.data
        p = self.src_tree.insert('', 'end', text=tr('grp_repo'), values=('',), open=True)
        for name, c in d.get('centers', {}).items():
            iid = self.src_tree.insert(p, 'end', text=name,
                                       values=(c.get('kind', ''),), open=True)
            self._src_map[iid] = ('center', name)
            for field in ('api', 'obs', 'nav', 'prod', 'mgex', 'ion'):
                v = c.get(field, '')
                if v:
                    self.src_tree.insert(iid, 'end', text='  ' + field, values=(v,))
        p = self.src_tree.insert('', 'end', text=tr('grp_ac'), values=('',), open=False)
        for i, ac in enumerate(d.get('analysis_centers', [])):
            series = '/'.join(tr(s) for s in SERIES_IDS if ac.get('series', {}).get(s))
            iid = self.src_tree.insert(p, 'end', text='%s (%s)' % (ac['name'], ac['id']),
                                       values=(('MGEX ' if ac.get('mgex') else '') + series,))
            self._src_map[iid] = ('ac', i)
        p = self.src_tree.insert('', 'end', text=tr('grp_ionex'), values=('',), open=False)
        for i, ion in enumerate(d.get('ionex', [])):
            iid = self.src_tree.insert(p, 'end', text='%s %s' % (ion['id'], ion['name']),
                                       values=('',))
            self._src_map[iid] = ('ionex', i)
        p = self.src_tree.insert('', 'end', text=tr('grp_hfile'), values=('',), open=True)
        for i, h in enumerate(d.get('hfile', [])):
            iid = self.src_tree.insert(p, 'end', text=h['name'],
                                       values=('',), open=len(h.get('urls', [])) > 1)
            self._src_map[iid] = ('hfile', i)
            for j, u in enumerate(h.get('urls', [])):
                self.src_tree.insert(iid, 'end', text='  url%d' % (j + 1), values=(u,))
        p = self.src_tree.insert('', 'end', text=tr('grp_region'), values=('',), open=True)
        for i, r in enumerate(d.get('regional', [])):
            iid = self.src_tree.insert(p, 'end', text=r['name'],
                                       values=('',), open=len(r.get('templates', [])) > 1)
            self._src_map[iid] = ('regional', i)
            for j, t in enumerate(r.get('templates', [])):
                self.src_tree.insert(iid, 'end', text='  tpl%d' % (j + 1), values=(t,))

    def _src_selected(self):
        sel = self.src_tree.selection()
        if not sel:
            messagebox.showinfo(tr('msg_tip'), tr('msg_pick_source'))
            return None
        iid = sel[0]
        if iid not in self._src_map:
            iid = self.src_tree.parent(iid)          # 子节点 -> 回退父节点
        if not iid or iid not in self._src_map:
            messagebox.showinfo(tr('msg_tip'), tr('msg_pick_source'))
            return None
        return iid, self._src_map[iid]

    def _src_edit(self):
        s = self._src_selected()
        if not s:
            return
        iid, (kind, key) = s
        d = self.src.data
        if kind == 'center':
            c = d['centers'][key]
            r = FormDialog(self, key, [
                ('api', 'API/list', 'entry'), ('obs', 'obs', 'entry'),
                ('nav', 'nav', 'entry'), ('prod', 'prod', 'entry'),
                ('mgex', 'mgex', 'entry'), ('ion', 'ionex', 'entry')], values=c)
            if r.result:
                for k, v in r.result.items():
                    c[k] = v
                self._after_sources_changed()
        elif kind == 'ac':
            ac = d['analysis_centers'][key]
            flat = {'fin': '', 'rap': '', 'ult': ''}
            for s_ in SERIES_IDS:
                flat[s_] = ','.join(ac.get('series', {}).get(s_, []))
            r = FormDialog(self, ac['name'], [
                ('id', 'id', 'entry'), ('name', 'name', 'entry'),
                ('mgex', 'MGEX', 'check'),
                ('fin', tr('fin') + ' (orb,clk,erp,snx,bia)', 'entry'),
                ('rap', tr('rap'), 'entry'), ('ult', tr('ult'), 'entry')],
                values={'id': ac['id'], 'name': ac['name'], 'mgex': ac.get('mgex'),
                        'fin': flat['fin'], 'rap': flat['rap'], 'ult': flat['ult']})
            if r.result:
                ac['id'] = r.result['id'] or ac['id']
                ac['name'] = r.result['name'] or ac['name']
                ac['mgex'] = bool(r.result['mgex'])
                for s_ in SERIES_IDS:
                    pts = [x.strip() for x in r.result[s_].split(',') if x.strip()]
                    if pts:
                        ac.setdefault('series', {})[s_] = pts
                    elif s_ in ac.get('series', {}):
                        del ac['series'][s_]
                self._after_sources_changed()
        elif kind == 'ionex':
            ion = d['ionex'][key]
            r = FormDialog(self, 'IONEX', [('id', 'id', 'entry'),
                                           ('name', 'name', 'entry')], values=ion)
            if r.result:
                ion.update({k: v for k, v in r.result.items() if v})
                self._after_sources_changed()
        elif kind == 'hfile':
            h = d['hfile'][key]
            r = FormDialog(self, 'hfile', [
                ('id', 'id', 'entry'), ('name', 'name', 'entry'),
                ('by', 'by', 'combo:day,year'),
                ('urls', 'urls', 'text')],
                values={'id': h['id'], 'name': h['name'], 'by': h.get('by', 'day'),
                        'urls': '\n'.join(h.get('urls', []))})
            if r.result:
                h['id'] = r.result['id'] or h['id']
                h['name'] = r.result['name'] or h['name']
                h['by'] = r.result['by'] or 'day'
                h['urls'] = [x.strip() for x in r.result['urls'].splitlines() if x.strip()]
                self._after_sources_changed()
        elif kind == 'regional':
            rg = d['regional'][key]
            r = FormDialog(self, rg['name'], [
                ('id', 'id', 'entry'), ('name', 'name', 'entry'),
                ('templates', 'templates ({SSSS})', 'text'),
                ('stations', 'stations', 'text'),
                ('user', tr('src_user'), 'entry'), ('pass', tr('src_pass'), 'entry')],
                values={'id': rg['id'], 'name': rg['name'],
                        'templates': '\n'.join(rg.get('templates', [])),
                        'stations': '\n'.join(rg.get('stations', [])),
                        'user': rg.get('user', ''),
                        'pass': dec(rg.get('pass', '')) if rg.get('pass') else ''})
            if r.result:
                rg['id'] = r.result['id'] or rg['id']
                rg['name'] = r.result['name'] or rg['name']
                rg['templates'] = [x.strip() for x in r.result['templates'].splitlines() if x.strip()]
                rg['stations'] = [x for x in re.split(r'[\s,;，；]+', r.result['stations']) if x]
                rg['user'] = r.result.get('user', '').strip()
                rg['pass'] = enc(r.result.get('pass', '').strip())
                self._after_sources_changed()

    def _src_add(self):
        """新增跟随选中类别；产品类（存储库/机构/IONEX）为封闭集合不可新增。"""
        sel = self.src_tree.selection()
        kind = None
        if sel:
            iid = sel[0]
            node = self._src_map.get(iid)
            if node:
                kind = node[0]
            else:                                   # 选中的是分组标题
                txt = self.src_tree.item(iid, 'text')
                if txt == tr('grp_region'):
                    kind = 'regional'
                elif txt == tr('grp_hfile'):
                    kind = 'hfile'
        if kind in ('center', 'ac', 'ionex'):
            messagebox.showinfo(tr('msg_tip'), tr('msg_closed_add'))
            return
        if kind is None:
            kind = 'regional'
        d = self.src.data
        if kind == 'hfile':
            r = FormDialog(self, 'hfile +', [
                ('id', 'id', 'entry'), ('name', 'name', 'entry'),
                ('by', 'by', 'combo:day,year'), ('urls', 'urls', 'text')])
            if r.result and r.result.get('id'):
                d.setdefault('hfile', []).append({
                    'id': r.result['id'], 'name': r.result['name'] or r.result['id'],
                    'by': r.result['by'] or 'day',
                    'urls': [x.strip() for x in r.result['urls'].splitlines() if x.strip()]})
                self._after_sources_changed()
        else:
            r = FormDialog(self, tr('grp_region') + ' +', [
                ('id', 'id', 'entry'), ('name', 'name', 'entry'),
                ('templates', 'templates ({SSSS})', 'text'),
                ('stations', 'stations', 'text'),
                ('user', tr('src_user'), 'entry'), ('pass', tr('src_pass'), 'entry')])
            if r.result and r.result.get('id'):
                d.setdefault('regional', []).append({
                    'id': r.result['id'], 'name': r.result['name'] or r.result['id'],
                    'templates': [x.strip() for x in r.result['templates'].splitlines() if x.strip()],
                    'stations': [x for x in re.split(r'[\s,;，；]+', r.result['stations']) if x],
                    'user': r.result.get('user', '').strip(),
                    'pass': enc(r.result.get('pass', '').strip())})
                self._after_sources_changed()

    def _src_del(self):
        s = self._src_selected()
        if not s:
            return
        iid, (kind, key) = s
        if not messagebox.askyesno(tr('msg_confirm'), tr('msg_confirm_del')):
            return
        d = self.src.data
        if kind == 'center':
            d['centers'].pop(key, None)
        elif kind == 'ac':
            d['analysis_centers'].pop(key)
        elif kind == 'ionex':
            d['ionex'].pop(key)
        elif kind == 'hfile':
            d['hfile'].pop(key)
        elif kind == 'regional':
            d['regional'].pop(key)
        self._build_sources_tree()

    def _src_reset(self):
        if messagebox.askyesno(tr('msg_confirm'), tr('msg_reset_src')):
            self.src.reset()
            self._after_sources_changed()

    def _src_save(self):
        self.src.save()
        self._after_sources_changed()
        self.log('数据源已保存到 sources.json')

    def _after_sources_changed(self):
        self._build_sources_tree()
        self._build_product_tree()
        self._build_hfile_body()
        self._build_region_body(True)
        repos = [k for k, v in self.src.centers().items() if v.get('kind') != 'aiubweb']
        self.igs_center['values'] = repos
        if self.igs_center.get() not in repos and repos:
            self.igs_center.set(repos[0])
        self.http.reset()

    # ---------------- 设置页 ----------------
    def _tab_settings(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text=tr('tab_settings'))
        g = ttk.Frame(f)
        g.pack(fill='x', padx=10, pady=8)

        def row(label, default='', show=None, width=42):
            r = ttk.Frame(g)
            r.pack(fill='x', pady=3)
            ttk.Label(r, text=label, width=26).pack(side='left')
            e = ttk.Entry(r, width=width, show=show)
            e.insert(0, default)
            e.pack(side='left')
            return e

        r = ttk.Frame(g)
        r.pack(fill='x', pady=3)
        ttk.Label(r, text=tr('set_root'), width=26).pack(side='left')
        self.set_root = ttk.Entry(r, width=42)
        self.set_root.insert(0, self.cfg.data['root_dir'])
        self.set_root.pack(side='left')
        ttk.Button(r, text=tr('set_browse'), command=self._browse_root).pack(side='left', padx=4)

        self.set_threads = row(tr('set_threads'), str(self.cfg.data['threads']), width=8)
        self.set_retry = row(tr('set_retry'), str(self.cfg.data['retry']), width=8)
        self.set_timeout = row(tr('set_timeout'), str(self.cfg.data['timeout']), width=8)
        self.set_proxy = row(tr('set_proxy'), self.cfg.data.get('proxy', ''))
        ttk.Label(g, text=tr('set_proxy_hint'), foreground='gray',
                  wraplength=620, justify='left').pack(anchor='w', padx=(26, 0))
        # 界面语言
        r = ttk.Frame(g)
        r.pack(fill='x', pady=3)
        ttk.Label(r, text=tr('set_lang'), width=26).pack(side='left')
        self.lang_var = tk.StringVar(value='中文' if _LANG[0] == 'zh' else 'English')
        cb = ttk.Combobox(r, textvariable=self.lang_var, state='readonly',
                          width=12, values=['中文', 'English'])
        cb.pack(side='left')
        cb.bind('<<ComboboxSelected>>', lambda e: self._switch_lang())
        ttk.Label(g, text=tr('set_ed_head'), foreground='gray').pack(anchor='w', pady=(10, 2))
        self.set_ed_user = row(tr('set_ed_user'), self.cfg.data.get('earthdata_user', ''))
        self.set_ed_pass = row(tr('set_ed_pass'), dec(self.cfg.data.get('earthdata_pass', '')),
                               show='*')
        self.gunzip_var = tk.BooleanVar(value=bool(self.cfg.data.get('auto_gunzip')))
        ttk.Checkbutton(g, text=tr('set_gunzip'), variable=self.gunzip_var).pack(anchor='w', pady=2)
        self.crx2rnx_var = tk.BooleanVar(value=bool(self.cfg.data.get('auto_crx2rnx')))
        ttk.Checkbutton(g, text=tr('set_crx2rnx'), variable=self.crx2rnx_var).pack(anchor='w', pady=2)
        self.force_var = tk.BooleanVar(value=bool(self.cfg.data.get('force_recheck_missing')))
        ttk.Checkbutton(g, text=tr('set_force'), variable=self.force_var).pack(anchor='w', pady=6)
        br = ttk.Frame(g)
        br.pack(fill='x', pady=6)
        ttk.Button(br, text=tr('set_save'), command=self._save_settings).pack(side='left')
        ttk.Button(br, text=tr('set_test'), command=self._test_earthdata).pack(side='left', padx=8)
        ttk.Button(br, text=tr('set_speed'), command=self._speed_test).pack(side='left', padx=8)

    def _switch_lang(self):
        want = 'zh' if self.lang_var.get() == '中文' else 'en'
        if want == _LANG[0]:
            return
        self._save_settings()          # 重建界面前落盘，避免丢未保存输入
        _LANG[0] = want
        self.cfg.data['lang'] = want
        self.cfg.data['ui'] = self._collect_ui()
        self.cfg.save()
        self._build_ui()
        self._restore_ui()

    def _browse_root(self):
        d = filedialog.askdirectory()
        if d:
            self.set_root.delete(0, 'end')
            self.set_root.insert(0, d)

    def _save_settings(self):
        d = self.cfg.data
        d['root_dir'] = self.set_root.get().strip() or APP_DIR
        try:
            d['threads'] = max(1, int(self.set_threads.get() or 4))
            d['retry'] = max(0, int(self.set_retry.get() or 2))
            d['timeout'] = max(5, int(self.set_timeout.get() or 30))
        except ValueError:
            pass
        d['proxy'] = _norm_proxy(self.set_proxy.get())
        self.set_proxy.delete(0, 'end')
        self.set_proxy.insert(0, d['proxy'])
        d['earthdata_user'] = self.set_ed_user.get().strip()
        d['earthdata_pass'] = enc(self.set_ed_pass.get().strip())
        d['force_recheck_missing'] = bool(self.force_var.get())
        d['auto_gunzip'] = bool(self.gunzip_var.get())
        d['auto_crx2rnx'] = bool(self.crx2rnx_var.get())
        self.thr_var.set(str(d.get('threads', 4)))
        d['ui'] = self._collect_ui()
        self.cfg.save()
        self.http.reset()
        self.log('设置已保存到 config.json')

    def _test_earthdata(self):
        self._save_settings()

        def proxy_note():
            px = _norm_proxy(self.cfg.data.get('proxy'))
            if px:
                return tr('proxy_used') % px
            return tr('proxy_direct')

        def work():
            try:
                # 用一个确定存在的小数据文件：认证成功返回二进制，失败才跳登录页
                url = 'https://cddis.nasa.gov/archive/gnss/products/ionex/2024/001/codg0010.24i.Z'
                req = urllib.request.Request(url, headers={'User-Agent': _UA})
                r = self.http._opener().open(req, timeout=self.http._tmo(url, 30))
                head = r.read(64)
                final = r.geturl()
                r.close()
                if ('/login' in final or 'urs.earthdata.nasa.gov' in final
                        or head.lstrip()[:1] == b'<'):
                    # 被 302 到登录页：账号密码错或未生效（不是真成功）
                    self.log('Earthdata 认证未生效（跳到登录页）')
                    self.after(0, lambda: messagebox.showerror(tr('set_test'), tr('test_badauth')))
                    return
                self.log('Earthdata 登录成功 (CDDIS 可访问)')
                self.after(0, lambda: messagebox.showinfo(tr('set_test'), tr('test_ok')))
            except urllib.error.HTTPError as e:
                self.log('Earthdata 登录失败: HTTP %s' % e.code)
                if e.code in (401, 403):
                    msg = tr('test_badauth')
                else:
                    msg = '%s (HTTP %s)\n%s' % (tr('test_netfail'), e.code, proxy_note())
                self.after(0, lambda m=msg: messagebox.showerror(tr('set_test'), m))
            except Exception as e:
                self.log('Earthdata 登录失败: %s' % str(e)[:120])
                msg = '%s\n%s\n%s' % (tr('test_netfail'), str(e)[:100], proxy_note())
                self.after(0, lambda m=msg: messagebox.showerror(tr('set_test'), m))
        threading.Thread(target=work, daemon=True).start()

    def _tab_about(self):
        f = ttk.Frame(self.nb)
        self.nb.add(f, text=tr('tab_about'))
        g = ttk.Frame(f)
        g.pack(anchor='nw', padx=16, pady=14)
        ttk.Label(g, text=tr('app_title'), font=('', 12, 'bold')).pack(anchor='w', pady=(0, 8))
        ttk.Label(g, text=tr('about_dev')).pack(anchor='w', pady=2)
        ttk.Label(g, text=tr('about_aff')).pack(anchor='w', pady=2)
        ttk.Label(g, text='邮箱/Email: jiangzhsh@mail.sysu.edu.cn').pack(anchor='w', pady=2)
        ttk.Label(g, text=tr('about_src')).pack(anchor='w', pady=(10, 2))
        ttk.Label(g, text=tr('about_manuals')).pack(anchor='w', pady=(10, 2))
        br = ttk.Frame(g)
        br.pack(anchor='w')
        ttk.Button(br, text='使用说明.txt',
                   command=lambda: self._open_file('使用说明.txt')).pack(side='left', padx=(0, 8))
        ttk.Button(br, text='User Manual.txt',
                   command=lambda: self._open_file('User Manual.txt')).pack(side='left')

    def _open_file(self, name):
        p = _res_path(name)          # exe 同目录优先，否则用 exe 内置
        if os.path.exists(p):
            try:
                os.startfile(p)
            except Exception as e:
                self.log('打开失败: %s' % e)
        else:
            messagebox.showinfo(tr('msg_tip'), name + ': ' + tr('cf_notfound'))

    def _prd_open_repo(self, key):
        for iid in self.prd_tree.get_children():
            if self.prd_tree.item(iid, 'text').split()[0] == key:
                self.prd_tree.item(iid, open=True)
                self.prd_tree.see(iid)
                break

    def _speed_test(self, on_pick=None):
        """测速各存储库并弹窗展示；on_pick(key) 非空时提供「采用最快」。"""
        self._save_settings()          # 先落盘，确保用界面上的最新代理/账号
        centers = self.src.centers()
        targets = {}
        sample = placeholders(dt.date(2024, 1, 1))
        for ck, c in centers.items():
            kind = c.get('kind', 'dir')
            if kind == 'whuweb':
                targets[ck] = c.get('api', '') + 'download?year=2026'
            elif kind == 'aiubweb':
                targets[ck] = c.get('api', '') + 'CODE'
            else:
                u = fmt_url(c.get('obs', '') or c.get('prod', ''), sample)
                if u:
                    targets[ck] = u
        if not targets:
            return
        win = tk.Toplevel(self)
        win.title(tr('set_speed'))
        win.transient(self)
        tree = ttk.Treeview(win, columns=('repo', 'rtt', 'state'),
                            show='headings', height=len(targets))
        tree.heading('repo', text=tr('repo').rstrip(':'))
        tree.heading('rtt', text=tr('spd_col_rtt'))
        tree.heading('state', text=tr('spd_col_state'))
        tree.column('repo', width=100)
        tree.column('rtt', width=90, anchor='center')
        tree.column('state', width=160)
        tree.pack(fill='both', expand=True, padx=8, pady=8)
        for ck in targets:
            tree.insert('', 'end', iid=ck, values=(ck, '…', tr('spd_testing')))
        state = {'fastest': None}
        btnf = ttk.Frame(win)
        btnf.pack(fill='x', pady=(0, 8))
        if on_pick:
            def use_fastest():
                if state['fastest']:
                    on_pick(state['fastest'])
                win.destroy()
            ttk.Button(btnf, text=tr('spd_use'), command=use_fastest).pack(side='left', padx=8)
        ttk.Button(btnf, text='OK', command=win.destroy).pack(side='right', padx=8)

        def probe(item):
            ck, url = item
            return ck, self.http.measure(url)

        def work():
            with ThreadPoolExecutor(max_workers=len(targets)) as ex:
                results = list(ex.map(probe, targets.items()))
            ok = sorted([r for r in results if r[1] is not None], key=lambda r: r[1])
            bad = [r for r in results if r[1] is None]
            self.cfg.data['_order'] = [c for c, _ in ok + bad
                                       if centers.get(c, {}).get('kind') != 'aiubweb']
            self.cfg.save()

            def fill():
                if not win.winfo_exists():
                    return
                for iid in tree.get_children():
                    tree.delete(iid)
                for c, s in ok:
                    tree.insert('', 'end', iid=c, values=(c, '%.2f s' % s, 'OK'))
                for c, s in bad:
                    tree.insert('', 'end', iid=c, values=(c, '—', tr('spd_fail')))
                state['fastest'] = ok[0][0] if ok else None
                self.log('测速: ' + ', '.join(
                    ('%s %.1fs' % (c, s)) if s is not None else ('%s 不可达' % c)
                    for c, s in results))
            self.after(0, fill)
        threading.Thread(target=work, daemon=True).start()

    # ---------------- 勾选记忆 ----------------
    def _collect_ui(self):
        ui = {}
        try:
            ui['igs_obs'] = bool(self.igs_obs.get())
            ui['igs_nav'] = bool(self.igs_nav.get())
            ui['igs_center'] = self.igs_center.get()
            ui['igs_stations'] = [s[:4].lower() for s in self.igs_table.get_selected()]
            ui['prd_checked'] = ['|'.join(k) for k in self._prd_nodes.values()
                                 if any(self.prd_tree.set(iid, 'sel') == CHK_ON
                                        for iid, k2 in self._prd_nodes.items() if k2 == k)]
            ui['hf'] = {i: (v.get(), e.get()) for i, (v, e) in self.hf_vars.items()}
            ui['rg_enable'] = {i: v.get() for i, v in self.rg_enable.items()}
            ui['rg_stations'] = {i: [s[:4].lower() for s in tb.get_selected()]
                                 for i, tb in self.rg_tables.items()}
            ui['rg_collapsed'] = dict(getattr(self, '_rg_collapsed', {}))
            # 用户手工添加的站写回源定义，随配置保存
            ch = False
            for rdef in self.src.data.get('regional', []):
                tb = self.rg_tables.get(rdef['id'])
                if tb:
                    newst = [tb.tree.item(i, 'text') for i in tb._station_rows()]
                    if newst != rdef.get('stations', []):
                        rdef['stations'] = newst
                        ch = True
            if ch:
                self.src.save()
        except Exception:
            pass
        return ui

    def _restore_ui(self):
        ui = self.cfg.data.get('ui') or {}
        try:
            self.igs_obs.set(bool(ui.get('igs_obs')))
            self.igs_nav.set(bool(ui.get('igs_nav')))
            vals = list(self.igs_center['values'])
            # 兼容旧记录里的 '自动'/'Auto'
            saved = ui.get('igs_center')
            if saved in ('自动', 'Auto') and vals:
                self.igs_center.set(vals[0])
            elif saved in vals:
                self.igs_center.set(saved)
            if ui.get('igs_stations'):
                self.igs_table.set_checked(ui['igs_stations'])
            saved = set(ui.get('prd_checked') or [])
            for iid, key in self._prd_nodes.items():
                if '|'.join(key) in saved:
                    self.prd_tree.set(iid, 'sel', CHK_ON)
            self._prd_refresh()
            for i, (en, pre) in (ui.get('hf') or {}).items():
                if i in self.hf_vars:
                    self.hf_vars[i][0].set(bool(en))
                    self.hf_vars[i][1].delete(0, 'end')
                    self.hf_vars[i][1].insert(0, pre)
            for i, en in (ui.get('rg_enable') or {}).items():
                if i in self.rg_enable:
                    self.rg_enable[i].set(bool(en))
            for i, keys in (ui.get('rg_stations') or {}).items():
                if i in self.rg_tables:
                    self.rg_tables[i].set_checked(keys)
        except Exception:
            pass

    # ---------------- 底部: 进度 / 日志 / 统计 ----------------
    def _bottom(self):
        f = ttk.Frame(self)
        f.pack(fill='both', padx=6, pady=(0, 6))
        self.bottom_frame = f
        bar = ttk.Frame(f)
        bar.pack(fill='x')
        self.btn_start = ttk.Button(bar, text=tr('btn_start'), command=self.start)
        self.btn_start.pack(side='left')
        self.btn_stop = ttk.Button(bar, text=tr('btn_stop'), command=self.stop, state='disabled')
        self.btn_stop.pack(side='left', padx=6)
        ttk.Label(bar, text=tr('threads')).pack(side='left', padx=(8, 2))
        self.thr_var = tk.StringVar(value=str(self.cfg.data.get('threads', 4)))
        tk.Spinbox(bar, from_=1, to=16, width=3, textvariable=self.thr_var).pack(side='left')
        self.thr_var.trace_add('write', lambda *a: self._sync_thr())
        self.prog = ttk.Progressbar(bar, length=240, mode='determinate')
        self.prog.pack(side='left', padx=8)
        self.prog_txt = ttk.Label(bar, text=tr('ready'))
        self.prog_txt.pack(side='left')
        self.prog_file = ttk.Label(f, text='', foreground='#2b6cb0')
        self.prog_file.pack(fill='x', pady=(2, 0))

        bnb = ttk.Notebook(f)
        bnb.pack(fill='both', expand=True, pady=(2, 0))
        self.bottom_nb = bnb
        lf = ttk.Frame(bnb)
        bnb.add(lf, text=tr('tab_log'))
        self.logw = tk.Text(lf, height=10, wrap='none')
        self.logw.pack(fill='both', expand=True)
        self.logw.config(state='disabled')
        sf = ttk.Frame(bnb)
        bnb.add(sf, text=tr('tab_stat'))
        self.stat_summary = ttk.Label(sf, text=tr('stat_idle'))
        self.stat_summary.pack(anchor='w', padx=4, pady=2)
        self.stat_tree = ttk.Treeview(sf, columns=('file', 'st', 'why'), show='headings', height=6)
        self.stat_tree.heading('file', text=tr('col_file'))
        self.stat_tree.heading('st', text=tr('col_state'))
        self.stat_tree.heading('why', text=tr('col_why'))
        self.stat_tree.column('file', width=430)
        self.stat_tree.column('st', width=70, anchor='center', stretch=False)
        self.stat_tree.column('why', width=180)
        self.stat_tree.pack(fill='both', expand=True, side='left', padx=4)
        ssb = ttk.Scrollbar(sf, orient='vertical', command=self.stat_tree.yview)
        self.stat_tree.configure(yscrollcommand=ssb.set)
        ssb.pack(side='left', fill='y')
        sbtns = ttk.Frame(sf)
        sbtns.pack(side='left', fill='y', padx=4)
        ttk.Button(sbtns, text=tr('btn_retry'), command=self._retry_failed).pack(pady=2)
        ttk.Button(sbtns, text=tr('btn_report'), command=lambda: os.startfile(
            os.path.join(APP_DIR, 'logs'))).pack(pady=2)

    def log(self, msg):
        self.q.put(('log', msg))

    def _pump(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == 'log':
                    self.logw.config(state='normal')
                    self.logw.insert('end', time.strftime('%H:%M:%S ') + str(val) + '\n')
                    self.logw.see('end')
                    self.logw.config(state='disabled')
                elif kind == 'prog':
                    done, total = val
                    self.prog['maximum'] = total
                    self.prog['value'] = done
                    self.prog_txt.config(text='%d / %d' % (done, total))
                elif kind == 'fprog':
                    label, done_b, total_b, speed = val
                    if done_b < 0:
                        self._active.pop(label, None)
                    else:
                        self._active[label] = (done_b, total_b, speed)
                    self._update_file_line()
                elif kind == 'stats':
                    self._fill_stats(val)
                elif kind == 'done':
                    self.btn_start.config(state='normal')
                    self.btn_stop.config(state='disabled')
                    self.prog_file.config(text='')
                    self._active.clear()
        except queue.Empty:
            pass
        self.after(150, self._pump)

    def _on_tab_changed(self, _evt=None):
        try:
            idx = self.nb.index(self.nb.select())
        except Exception:
            return
        if idx >= 4:     # 数据源管理/设置/关于：无下载控制区
            self.bottom_frame.pack_forget()
        elif not self.bottom_frame.winfo_ismapped():
            self.bottom_frame.pack(fill='both', padx=6, pady=(0, 6))

    def _sync_thr(self):
        """底部线程 Spinbox 改动即时同步到设置页输入框"""
        try:
            v = max(1, min(16, int(self.thr_var.get())))
        except (ValueError, tk.TclError):
            return
        try:
            if self.set_threads.get().strip() != str(v):
                self.set_threads.delete(0, 'end')
                self.set_threads.insert(0, str(v))
        except Exception:
            pass

    def _on_close(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno(tr('msg_tip'), tr('msg_quit_dl')):
                return
            self.stop()
        try:
            self._save_settings()      # 关窗自动保存，避免未保存的设置丢失
        except Exception:
            pass
        self.destroy()

    def _update_file_line(self):
        if not self._active:
            self.prog_file.config(text='')
            return
        label, (done_b, total_b, speed) = next(reversed(self._active.items()))
        mb = lambda b: '%.1fMB' % (b / 1048576)
        if total_b > 0:
            txt = '%s  %s/%s (%.0f%%)  %.0f KB/s' % (
                label, mb(done_b), mb(total_b), done_b * 100 / total_b, speed / 1024)
        else:
            txt = '%s  %s  %.0f KB/s' % (label, mb(done_b), speed / 1024)
        n = len(self._active)
        if n > 1:
            txt = '(%d) ' % n + txt
        self.prog_file.config(text=txt)

    # ---------------- 统计页 ----------------
    def _fill_stats(self, results):
        ok = len(results['ok'])
        ne = len(results['notexist'])
        skip = len(results['skipped'])
        cats = {}
        for item in results['failed']:
            k = classify_fail(item[1])
            cats[k] = cats.get(k, 0) + 1
        parts = ['%s %d / %s %d / %s %d' % (tr('st_ok'), ok, tr('st_ne'), ne,
                                            tr('st_skip'), skip)]
        if cats:
            parts.append('%s %d（%s）' % (tr('st_fail'), sum(cats.values()), '，'.join(
                '%s %d' % (tr('cf_' + k), v) for k, v in cats.items())))
        else:
            parts.append('%s 0' % tr('st_fail'))
        self.stat_summary.config(text='  '.join(parts))
        self.stat_tree.delete(*self.stat_tree.get_children())
        for label in results['notexist']:
            self.stat_tree.insert('', 'end', values=(label, tr('st_ne'), tr('cf_notfound')))
        for item in results['failed']:
            label, err, rel = item
            self.stat_tree.insert('', 'end', values=(label, tr('st_fail'),
                                                     tr('cf_' + classify_fail(err))))
        self.bottom_nb.select(1)

    def _retry_failed(self):
        if not hasattr(self, 'engine') or not self.engine:
            return
        tasks = self.engine.retryable_failed()
        if not tasks:
            messagebox.showinfo(tr('msg_tip'), tr('msg_no_retry'))
            return
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(tr('msg_tip'), tr('msg_running'))
            return
        self.btn_start.config(state='disabled')
        self.btn_stop.config(state='normal')
        self.engine = Engine(self.cfg, self.hist, self.http, self.log,
                             lambda d, t: self.q.put(('prog', (d, t))),
                             lambda *a: self.q.put(('fprog', a)))

        def work():
            try:
                self.log('重下失败项 %d 个 ...' % len(tasks))
                self.engine.run(tasks)
                self.q.put(('stats', self.engine.results))
            finally:
                self.q.put(('done', None))
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    # ---------------- 地图选站 ----------------
    def _open_station_map(self):
        p_geo = geo_json_path()
        if not os.path.exists(p_geo):
            messagebox.showinfo(tr('msg_tip'), tr('msg_map_missing'))
            return
        try:
            with open(p_geo, 'r', encoding='utf-8') as f:
                data = f.read()
            json.loads(data)
            html = _build_map_html(data)
            out = os.path.join(APP_DIR, 'igs_map.html')
            with open(out, 'w', encoding='utf-8') as f:
                f.write(html)
            os.startfile(out)
            self.log('地图选站页面已打开: %s' % out)
        except Exception as e:
            messagebox.showerror(tr('msg_err'), str(e))

    # ---------------- 启动下载 ----------------
    def start(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(tr('msg_tip'), tr('msg_running'))
            return
        idx = self.nb.index(self.nb.select())
        gen = {0: self._gen_igs, 1: self._gen_products,
               2: self._gen_hfile, 3: self._gen_region}.get(idx)
        if gen is None:
            messagebox.showinfo(tr('msg_tip'), tr('tab_igs') + '/' + tr('tab_prod') +
                                '/' + tr('tab_hfile') + '/' + tr('tab_region'))
            return
        if self._needs_earthdata(idx):
            messagebox.showwarning(tr('msg_tip'), tr('msg_need_ed'))
            return
        try:
            d1, d2 = self.dates.get()
        except Exception as e:
            messagebox.showerror(tr('msg_err'), '%s: %s' % (tr('msg_err_date'), e))
            return
        self._save_settings()
        self.btn_start.config(state='disabled')
        self.btn_stop.config(state='normal')
        self.engine = Engine(self.cfg, self.hist, self.http, self.log,
                             lambda d, t: self.q.put(('prog', (d, t))),
                             lambda *a: self.q.put(('fprog', a)))

        def work():
            try:
                self.log('正在生成任务（读取目录列表，请稍候）...')
                tasks, missing = gen(d1, d2)
                for m in missing:
                    self.log('[不存在] ' + m)
                    self.engine.results['notexist'].append(m)
                if not tasks:
                    self.log('没有需要下载的文件')
                    self.q.put(('stats', self.engine.results))
                else:
                    self.log('共生成 %d 个下载任务' % len(tasks))
                    self.engine.run(tasks)
                    self.q.put(('stats', self.engine.results))
            except Exception as e:
                self.log('出错: %s' % e)
            finally:
                self.q.put(('done', None))
        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def _needs_earthdata(self, idx):
        """本次任务涉及 CDDIS 但未配置 Earthdata 账号时返回 True"""
        if self.cfg.data.get('earthdata_user') and dec(self.cfg.data.get('earthdata_pass', '')):
            return False
        if idx == 0:
            return self.igs_center.get() == 'CDDIS'
        if idx == 1:
            for iid, k in self._prd_nodes.items():
                if k[0] in ('prod', 'ionex') and k[1] == 'CDDIS' \
                        and self.prd_tree.set(iid, 'sel') == CHK_ON:
                    return True
        return False

    def stop(self):
        if hasattr(self, 'engine'):
            self.engine.stop_event.set()
            if hasattr(self, 'builder') and self.builder:
                self.builder.stop.set()
            self.log('正在停止...')

    def _mk_builder(self):
        self.builder = TaskBuilder(self.http, self.cfg, self.src, self.log,
                                   stop_event=self.engine.stop_event)
        return self.builder

    def _gen_igs(self, d1, d2):
        stations = self.igs_table.get_selected()
        if not stations and self.igs_obs.get():
            raise ValueError(tr('msg_need_sta'))
        if not self.igs_obs.get() and not self.igs_nav.get():
            raise ValueError(tr('msg_need_obsnav'))
        center = self.igs_center.get()
        return self._mk_builder().build_igs(d1, d2, stations, self.igs_obs.get(),
                                            self.igs_nav.get(), center)

    def _gen_products(self, d1, d2):
        try:
            d_end = dt.date(*[int(x) for x in d2.split('-')])
            if (dt.date.today() - d_end).days < 14:
                self.log('提示: 最终产品(final)通常延迟约2周发布，近两周的日期可能不存在')
        except Exception:
            pass
        prod = {}          # repo -> {(acid,series): set(pt)}
        ionex = {}         # repo -> set(ionid)
        aiub_items = set()
        for iid, key in self._prd_nodes.items():
            if self.prd_tree.set(iid, 'sel') != CHK_ON:
                continue
            if key[0] == 'prod':
                _, repo, acid, series, pt = key
                prod.setdefault(repo, {}).setdefault((acid, series), set()).add(pt)
            elif key[0] == 'ionex':
                _, repo, ionid = key
                ionex.setdefault(repo, set()).add(ionid)
            else:
                aiub_items.add(key[1])
        if not prod and not ionex and not aiub_items:
            raise ValueError(tr('msg_need_prod'))
        tb = self._mk_builder()
        tasks, missing = [], []
        for repo, sel in prod.items():
            t, m = tb.build_products(d1, d2, {k: sorted(v) for k, v in sel.items()}, repo)
            tasks += t
            missing += m
        for repo, ids in ionex.items():
            t, m = tb.build_ionex(d1, d2, sorted(ids), repo)
            tasks += t
            missing += m
        if aiub_items:
            t, m = tb.build_aiub(d1, d2, sorted(aiub_items))
            tasks += t
            missing += m
        return tasks, missing

    def _gen_hfile(self, d1, d2):
        tb = self._mk_builder()
        tasks, missing = [], []
        used = False
        for src in self.src.hfile():
            v, e = self.hf_vars.get(src['id'], (None, None))
            if v and v.get():
                used = True
                t, m = tb.build_hfile(d1, d2, src, e.get())
                tasks += t
                missing += m
        if not used:
            raise ValueError(tr('msg_need_hfile'))
        return tasks, missing

    def _gen_region(self, d1, d2):
        tb = self._mk_builder()
        tasks, missing = [], []
        for src in self.src.regional():
            if not self.rg_enable.get(src['id']) or not self.rg_enable[src['id']].get():
                continue
            stations = self.rg_tables[src['id']].get_selected()
            if not stations:
                continue
            t, m = tb.build_regional(d1, d2, src, stations)
            tasks += t
            missing += m
        if not tasks and not missing:
            raise ValueError(tr('msg_need_region'))
        return tasks, missing


def _build_map_html(data):
    """生成自包含地图 html：leaflet js/css 内联，css 中图片转 base64 data URI。"""
    ld = _res_path('leaflet')
    with open(os.path.join(ld, 'leaflet.css'), 'r', encoding='utf-8') as f:
        css = f.read()
    for img in ('layers.png', 'layers-2x.png', 'marker-icon.png',
                'marker-icon-2x.png', 'marker-shadow.png'):
        ip = os.path.join(ld, 'images', img)
        if os.path.exists(ip):
            with open(ip, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('ascii')
            css = css.replace('images/%s' % img, 'data:image/png;base64,' + b64)
    with open(os.path.join(ld, 'leaflet.js'), 'r', encoding='utf-8') as f:
        js = f.read()
    return (MAP_TEMPLATE.replace('__CSS__', css)
                        .replace('__JS__', js)
                        .replace('__DATA__', data))


MAP_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>IGS 测站地图选站</title>
<style>__CSS__</style>
<script>__JS__</script>
<style>
  html,body{margin:0;height:100%;font-family:"Microsoft YaHei",sans-serif}
  #map{position:absolute;left:0;top:0;bottom:0;right:260px}
  #side{position:absolute;right:0;top:0;bottom:0;width:260px;background:#f7f8fa;
        border-left:1px solid #ccc;display:flex;flex-direction:column;padding:8px;box-sizing:border-box}
  #side h3{margin:2px 0 8px;font-size:15px}
  #search{width:100%;box-sizing:border-box;padding:4px;margin-bottom:6px}
  #count{font-size:13px;color:#333;margin-bottom:6px}
  #list{flex:1;overflow:auto;background:#fff;border:1px solid #ddd;font-size:13px;
        padding:4px;white-space:pre-line;word-break:break-all}
  .btn{margin-top:6px;padding:7px;font-size:13px;cursor:pointer;border:1px solid #888;
       background:#fff;border-radius:4px}
  .btn:hover{background:#e8eef7}
  #copyBtn{background:#2b6cb0;color:#fff;border-color:#2a5a8c;font-weight:bold}
  #copyBtn:hover{background:#25598f}
  #tip{font-size:11px;color:#888;margin-top:6px;line-height:1.5}
</style>
</head>
<body>
<div id="map"></div>
<div id="side">
  <h3>IGS 测站地图选站</h3>
  <input id="search" placeholder="搜索站名/国家码，回车定位">
  <select id="basemap" class="btn" style="width:100%;margin-bottom:6px">
    <option value="0">底图: 高德地图</option>
    <option value="1">底图: ESRI 街道图</option>
    <option value="2">底图: ESRI 卫星影像</option>
    <option value="3">底图: OpenStreetMap</option>
  </select>
  <div id="count">已选 <b id="nsel">0</b> 个站</div>
  <div id="list">（点击地图上的圆点选择测站）</div>
  <button class="btn" id="copyBtn">复制选中站名到剪贴板</button>
  <button class="btn" id="clearBtn">清空选择</button>
  <div id="tip">复制后回到下载器，点「粘贴导入」即可勾选。<br>
  红色=已选，蓝色=未选。底图加载失败会自动切换，也可用上方下拉框手动换。<br>
  注：高德底图国内有坐标偏移，放大后点位偏几百米属正常现象，选站不受影响。</div>
</div>
<script>
if (typeof L === 'undefined') {
  document.body.innerHTML = '<p style="padding:24px;font-size:15px">地图组件加载失败 / Map component failed to load.</p>';
  throw new Error('leaflet missing');
}
var STATIONS = __DATA__;
var map = L.map('map').setView([33, 108], 3);
var BASEMAPS = [
  {name: '高德地图', url: 'https://webr0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}',
   opt: {subdomains: '1234', attribution: '&copy; 高德地图'}},
  {name: 'ESRI 街道图', url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}',
   opt: {attribution: '&copy; Esri'}},
  {name: 'ESRI 卫星影像', url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
   opt: {attribution: '&copy; Esri'}},
  {name: 'OpenStreetMap', url: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
   opt: {attribution: '&copy; OpenStreetMap'}}
];
var bi = 0, errCount = 0, curLayer = null;
function addBasemap(i, manual){
  bi = i;
  if (curLayer) map.removeLayer(curLayer);
  errCount = 0;
  curLayer = L.tileLayer(BASEMAPS[i].url, Object.assign({maxZoom: 18}, BASEMAPS[i].opt));
  curLayer.on('tileload', function(){ errCount = 0; });
  curLayer.on('tileerror', function(){
    errCount++;
    if (errCount >= 4 && bi < BASEMAPS.length - 1) {
      addBasemap(bi + 1, false);
    }
  });
  curLayer.addTo(map);
  document.getElementById('basemap').value = String(i);
}
document.getElementById('basemap').addEventListener('change', function(){
  addBasemap(parseInt(this.value, 10), true);
});
addBasemap(0, false);

var selected = {}, markers = {};
function refreshSide(){
  var keys = Object.keys(selected).sort();
  document.getElementById('nsel').textContent = keys.length;
  document.getElementById('list').textContent = keys.length ? keys.join(', ') : '（点击地图上的圆点选择测站）';
}
function toggle(st, m){
  var k = st.s;
  if (selected[k]) { delete selected[k]; m.setStyle({color:'#2166d1', fillColor:'#3a7bd5'}); }
  else { selected[k] = st; m.setStyle({color:'#c0392b', fillColor:'#e74c3c'}); }
  refreshSide();
}
STATIONS.forEach(function(st){
  var m = L.circleMarker([st.lat, st.lon], {radius: 6, weight: 1.5,
      color: '#2166d1', fillColor: '#3a7bd5', fillOpacity: 0.75});
  m.bindTooltip(st.n9 + ' (' + st.cc + ')', {direction: 'top'});
  m.on('click', function(){ toggle(st, m); });
  m.addTo(map);
  markers[st.s] = {st: st, m: m};
});
document.getElementById('clearBtn').onclick = function(){
  Object.keys(selected).forEach(function(k){
    markers[k].m.setStyle({color:'#2166d1', fillColor:'#3a7bd5'});
  });
  selected = {}; refreshSide();
};
document.getElementById('copyBtn').onclick = function(){
  var text = Object.keys(selected).sort().join(', ');
  if (!text) { alert('还没有选择测站'); return; }
  function done(){ alert('已复制 ' + Object.keys(selected).length + ' 个站名！\n回到下载器点「粘贴导入」'); }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done, function(){ fallback(); });
  } else { fallback(); }
  function fallback(){
    var ta = document.createElement('textarea');
    ta.value = text; document.body.appendChild(ta); ta.select();
    document.execCommand('copy'); document.body.removeChild(ta); done();
  }
};
document.getElementById('search').addEventListener('keydown', function(e){
  if (e.key !== 'Enter') return;
  var q = this.value.trim().toLowerCase(); if (!q) return;
  for (var k in markers) {
    var st = markers[k].st;
    if (st.s === q || st.n9.toLowerCase().indexOf(q) === 0 || st.cc.toLowerCase() === q) {
      map.setView([st.lat, st.lon], 8);
      markers[k].m.bindTooltip(st.n9 + ' (' + st.cc + ')').openTooltip();
      return;
    }
  }
  alert('未找到: ' + q);
});
refreshSide();
</script>
</body>
</html>
"""


def _single_instance():
    """文件字节锁：已有一个实例在运行时返回 False（进程退出锁自动释放）"""
    try:
        import msvcrt
        fd = os.open(os.path.join(APP_DIR, '.gnss.lock'), os.O_CREAT | os.O_RDWR)
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)               # 非阻塞锁首字节
        _single_instance._fd = fd                            # 持有防回收
    except OSError:
        return False                                         # 锁被占 = 已有实例
    except Exception:
        pass                                                 # 其他异常不阻塞启动
    return True


def main():
    if not _single_instance():
        r = tk.Tk()
        r.withdraw()
        messagebox.showinfo(tr('app_title'), tr('msg_already'))
        r.destroy()
        return
    app = App()
    app.mainloop()


if __name__ == '__main__':
    main()
