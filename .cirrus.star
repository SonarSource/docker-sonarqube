load("github.com/SonarSource/cirrus-modules@v3", "load_features")
load("cirrus", "env", "fs", "yaml")

def main(ctx):
    return yaml.dumps(load_features(ctx)) + fs.read(".cirrus/tasks.yml")
