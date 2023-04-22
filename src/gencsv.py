import faker

fake = faker.Faker("en_US")

columns = ["full_name", "age", "phone", "position", "company"]
data = []

for _ in range(50):
    data.append([
        fake.name(),
        fake.pyint(18, 65),
        fake.phone_number(),
        fake.job(),
        fake.company(),
    ])

sep = ","
make_row = lambda cols, flag=False: f'{sep.join(repr(col) if flag else col for col in cols)}\n'

with open("data/employee.csv", mode="w+") as f:
    f.write(make_row(columns))
    for row in data:
        f.write(make_row(row, flag=True))