# Developing AI Apps in Azure Tips & Tricks Section

Just a collection of tips and tricks we accumulated that can help when
developing or troubleshooting an AI app in Azure.

## AZD

### Hooks

#### Use bash debug while developing hooks

Use this as your shebang when debugging or developing AZD hooks:

```
#!/bin/bash -x
```

Then run your hook specifically with :

```
azd hooks run preprovision
```
