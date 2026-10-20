"""
The "เก็บราคา" bookmarklet: a bookmark you click while YOU are looking at a
product page in your own browser. It reads the page you already have open
(title, link, picture, and the price you highlighted or the page's own price
metadata) and opens a small Price Bot window to confirm and save it.

It never loads anything from the marketplace by itself - so to the website
it is just you browsing normally.
"""
import json
from urllib.parse import quote

_SOURCE = r"""
(function(){
var B=__BASE__;
function m(n){var e=document.querySelector('meta[property="'+n+'"],meta[name="'+n+'"],meta[itemprop="'+n+'"]');return e?(e.getAttribute('content')||''):''}
var sel=String(window.getSelection?window.getSelection():'').trim();
var p='';
try{var ss=document.querySelectorAll('script[type="application/ld+json"]');
for(var i=0;i<ss.length&&!p;i++){var d=JSON.parse(ss[i].textContent);var a=[].concat(d['@graph']||d);
for(var j=0;j<a.length&&!p;j++){var o=a[j]&&a[j].offers;if(o){o=[].concat(o)[0];p=String(o.price||o.lowPrice||'')}}}}catch(e){}
p=p||m('product:price:amount')||m('og:price:amount')||m('price');
var q=new URLSearchParams({url:location.href,title:m('og:title')||document.title,price:p,sel:sel.slice(0,300),image:m('og:image')});
window.open(B+'/capture?'+q.toString(),'pricebot','width=560,height=780');
})();
"""


def bookmarklet_href(base_url: str) -> str:
    base = base_url.rstrip("/") or "http://localhost:8000"
    code = _SOURCE.replace("__BASE__", json.dumps(base))
    code = "".join(line.strip() for line in code.strip().splitlines())
    return "javascript:" + quote(code, safe="")
