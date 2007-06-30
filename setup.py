from distutils.core import setup
setup(name='peapod',
      version='0.6',
      py_modules=['Peapod.peapod','Peapod.tagging','Peapod.OPML','Peapod.btclient','Peapod.feedparser'],
      scripts=['peapod.py','btclient.py'],
      )
