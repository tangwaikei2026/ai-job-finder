from src.raw.collectors.alibaba import AlibabaBaseCollector
from src.raw.collectors.baidu import BaiduRawCollector
from src.raw.collectors.bytedance import ByteDanceRawCollector
from src.raw.collectors.didi import DidiRawCollector
from src.raw.collectors.feishu import FeishuRawCollector
from src.raw.collectors.kuaishou import KuaishouRawCollector
from src.raw.collectors.liepin import LiepinRawCollector
from src.raw.collectors.meituan import MeituanRawCollector
from src.raw.collectors.netease import NeteaseRawCollector
from src.raw.collectors.quark import QuarkRawCollector
from src.raw.collectors.tencent import TencentRawCollector
from src.raw.collectors.xiaohongshu import XiaohongshuRawCollector

COLLECTOR_REGISTRY = {
    "aliyun": AlibabaBaseCollector,
    "tongyi": AlibabaBaseCollector,
    "dingtalk": AlibabaBaseCollector,
    "baidu": BaiduRawCollector,
    "tencent": TencentRawCollector,
    "netease": NeteaseRawCollector,
    "quark": QuarkRawCollector,
    "feishu": FeishuRawCollector,
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
    "KuaishouRawCollector",
    "LiepinRawCollector",
    "MeituanRawCollector",
    "NeteaseRawCollector",
    "QuarkRawCollector",
    "TencentRawCollector",
    "XiaohongshuRawCollector",
]
