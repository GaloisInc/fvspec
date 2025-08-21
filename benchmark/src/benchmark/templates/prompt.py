from jinja2 import Environment, PackageLoader

env = Environment(loader=PackageLoader("generate"))

system = env.get_template("system.txt")
initial = env.get_template("initial.txt")
