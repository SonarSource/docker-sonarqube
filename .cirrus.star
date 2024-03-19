load("github.com/SonarSource/cirrus-modules@v2", "load_features")
load_features(ctx, aws=dict(env_type="dev"))

def main(ctx):
    return load_features(ctx)
