# -*- coding: utf-8 -*-
"""修复 Earthdata 认证：改 preemptive Basic + 测试登录假阳性修复"""
import io

P = 'gnss_downloader.py'
src = io.open(P, encoding='utf-8').read()

def rep(old, new):
    global src
    c = src.count(old)
    assert c == 1, 'anchor not unique (%d): %r' % (c, old[:60])
    src = src.replace(old, new)

# 1) _PreemptiveAuth 只对 https 发凭证（CDDIS 链中有一跳明文 http）
rep("""    def http_request(self, req):
        tok = self.creds.get(urllib.parse.urlparse(req.full_url).netloc)
        if tok and 'Authorization' not in req.headers:
            req.add_header('Authorization', tok)
        return req""",
    """    def http_request(self, req):
        if not req.full_url.startswith('https:'):
            return req                      # 明文 http 跳不送凭证
        tok = self.creds.get(urllib.parse.urlparse(req.full_url).netloc)
        if tok and 'Authorization' not in req.headers:
            req.add_header('Authorization', tok)
        return req""")

# 2) Earthdata 凭证并入 PreemptiveAuth（urs 是 302 登录页而非 401 挑战）
rep("""        # 区域网/hfile 数据源自带的账号（Basic 型）
        creds = {}""",
    """        # 区域网/hfile 数据源自带的账号（Basic 型）
        creds = {}
        if user and pw:
            # Earthdata 必须 preemptive：URS 用 302 跳登录页，从不发 401 挑战
            tok = 'Basic ' + base64.b64encode(('%s:%s' % (user, pw)).encode()).decode()
            creds['urs.earthdata.nasa.gov'] = tok
            creds['cddis.nasa.gov'] = tok""")

# 3) 测试登录：识别"跳到登录页"的假成功
rep("""        def work():
            try:
                url = 'https://cddis.nasa.gov/archive/gnss/products/ionex/2024/001/'
                b = self.http.get_bytes(url, timeout=30)
                self.log('Earthdata 登录成功 (CDDIS 可访问, %d 字节)' % len(b))
                self.after(0, lambda: messagebox.showinfo(tr('set_test'), tr('test_ok')))""",
    """        def work():
            try:
                url = 'https://cddis.nasa.gov/archive/gnss/products/ionex/2024/001/'
                req = urllib.request.Request(url, headers={'User-Agent': _UA})
                r = self.http._opener().open(req, timeout=self.http._tmo(url, 30))
                head = r.read(4096)
                final = urllib.parse.urlparse(r.geturl()).path
                r.close()
                if '/login' in final or head.lstrip()[:1] == b'<':
                    # 被 302 到登录页：账号密码错或未生效（不是真成功）
                    self.log('Earthdata 认证未生效（跳到登录页）')
                    self.after(0, lambda: messagebox.showerror(tr('set_test'), tr('test_badauth')))
                    return
                self.log('Earthdata 登录成功 (CDDIS 可访问)')
                self.after(0, lambda: messagebox.showinfo(tr('set_test'), tr('test_ok')))""")

io.open(P, 'w', encoding='utf-8', newline='').write(src)
print('patched OK')
