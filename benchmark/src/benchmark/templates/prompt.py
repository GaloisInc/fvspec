from jinja2 import Environment, PackageLoader

env = Environment(loader=PackageLoader("benchmark"))

system = env.get_template("system.prompt")
initial = env.get_template("initial.prompt.template")
