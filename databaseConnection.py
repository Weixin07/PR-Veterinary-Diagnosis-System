import psycopg2

conn = psycopg2.connect(host="localhost", dbname="postgres", user="postgres", password="1234", port=5432)

cur = conn.cursor()

# add database actions
cur.execute("""CREATE TABLE IF NOT EXISTS person(
            id INT PRIMARY KEY,
            name VARCHAR(255),
            age INT,
            gender CHAR
);
            """)

#cur.execute("""INSERT INTO person (id, name, age, gender) VALUES
 #           (1, 'MIKE', 30, 'm'),
  #          (2, 'POLASKI', 35, 'f'),            
   #         (3, 'JOHN', 25, 'm');
#""")

cur.execute("""SELECT * FROM person where name = 'POLASKI';""")
print(cur.fetchone())

cur.execute("""SELECT * FROM person WHERE age < 31;""")

for row in cur.fetchall():
    print(row)

sql = cur.mogrify("""SELECT * FROM person WHERE starts_with(name, %s) AND age < %s;""", ("J",50))
print(sql)
cur.execute(sql)
print(cur.fetchall())

conn.commit()

cur.close()
conn.close()