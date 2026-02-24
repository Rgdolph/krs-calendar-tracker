import psycopg2
c = psycopg2.connect('postgresql://krs_calendar_db_user:87GA8KEjZYd6vVIiSs9aqokIpInYgwDn@dpg-d6eg6b0gjchc73fcun70-a.oregon-postgres.render.com/krs_calendar_db')
cur = c.cursor()
cur.execute("DELETE FROM events WHERE week_key='test'")
c.commit()
print('cleaned')
c.close()
