from logging.handlers import TimedRotatingFileHandler


class PortalLoggingHandler(TimedRotatingFileHandler):
    def emit(self, record):
        record.ip = '0.0.0.0'
        try:
            request = record.args[0]
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                record.ip = x_forwarded_for.split(',')[-1].strip()
            elif request.META.get('HTTP_X_REAL_IP'):
                record.ip = request.META.get('HTTP_X_REAL_IP')
            else:
                record.ip = request.META.get('REMOTE_ADDR')
            record.args = None
        except:
            pass
        super(TimedRotatingFileHandler, self).emit(record)