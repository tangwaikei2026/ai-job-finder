from src.collectors.alibaba import AlibabaBaseCollector
from src.collectors.baidu import BaiduRawCollector
from src.collectors.bytedance import ByteDanceRawCollector
from src.collectors.didi import DidiRawCollector
from src.collectors.feishu import FeishuRawCollector
from src.collectors.jd import JDRawCollector
from src.collectors.kuaishou import KuaishouRawCollector
from src.collectors.liepin import LiepinRawCollector
from src.collectors.meituan import MeituanRawCollector
from src.collectors.netease import NeteaseRawCollector
from src.collectors.quark import QuarkRawCollector
from src.collectors.tencent import TencentRawCollector
from src.collectors.xiaohongshu import XiaohongshuRawCollector

COLLECTOR_REGISTRY = {
    "aliyun": AlibabaBaseCollector,
    "tongyi": AlibabaBaseCollector,
    "dingtalk": AlibabaBaseCollector,
    "baidu": BaiduRawCollector,
    "tencent": TencentRawCollector,
    "netease": NeteaseRawCollector,
    "quark": QuarkRawCollector,
    "feishu": FeishuRawCollector,
    "jd": JDRawCollector,
    "didi": DidiRawCollector,
    "bytedance": ByteDanceRawCollector,
    "meituan": MeituanRawCollector,
    "kuaishou": KuaishouRawCollector,
    "liepin": LiepinRawCollector,
    "xiaohongshu": XiaohongshuRawCollector,
}

__all__ = [
    "AlibabaBaseCollector",
    "BaiduRawCollector",
    "ByteDanceRawCollector",
    "COLLECTOR_REGISTRY",
    "DidiRawCollector",
    "FeishuRawCollector",
    "JDRawCollector",
    "KuaishouRawCollector",
    "LiepinRawCollector",
    "MeituanRawCollector",
    "NeteaseRawCollector",
    "QuarkRawCollector",
    "TencentRawCollector",
    "XiaohongshuRawCollector",
]
