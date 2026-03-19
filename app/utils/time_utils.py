from datetime import datetime
import pytz

# 定义中国时区
CHINA_TZ = pytz.timezone('Asia/Shanghai')

def now():
    """
    返回当前北京时间（带时区）
    """
    return datetime.now(CHINA_TZ)

def format_time(dt, fmt="%Y-%m-%d %H:%M:%S"):
    """
    格式化时间（用于展示）
    """
    if not dt:
        return ""

    # 如果是无时区时间，强制认为是中国时间
    if dt.tzinfo is None:
        dt = CHINA_TZ.localize(dt)

    return dt.strftime(fmt)