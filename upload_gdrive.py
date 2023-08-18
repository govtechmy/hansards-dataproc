import gspread

gc = gspread.service_account()

sh = gc.open("test")

print(sh.sheet1.get('A1'))

sh = gc.create('poppy')
sh.share('chooijqweb@gmail.com', perm_type='user', role='owner', notify=False)
sh.share(None, perm_type='anyone', role='writer', notify=False)