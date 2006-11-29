from distutils.core import setup
setup(name='peapod',
      version='xxx',
      py_modules=['Peapod.peapod','Peapod.tagging','Peapod.OPML','Peapod.btclient','Peapod.feedparser'],
      scripts=['peapod.py','btclient.py'],
      )
