from githubAsync import Repository

allowedLicenses = [
    'MIT',
    'MIT-0',
    'Apache-2.0',
    'ISC',
    '0BSD',
    'BSD-1-Clause',
    'BSD-2-Clause',
    'BSD-3-Clause',
    'Unlicense',
    'BlueOak-1.0.0',
    'CC0-1.0',
]

disallowedLicenses = [
    "AGPL-3.0",
    "GPL-3.0",
    "GPL-2.0",
    "LGPL-3.0",
    "LGPL-2.1",
    "MPL-2.0",
]

def has_legal_license(repo: Repository):
    try:
        # throws a 404 exception if the repo does not have a license
        # the legal understanding is that we have no right to code without a license
        licenseFile = repo.license
        # this case shouldn't happen
        if licenseFile is None:
            return False, "unknown"
        if licenseFile.spdx_id in allowedLicenses:
            return licenseFile.spdx_id,"ok"
        if licenseFile.spdx_id in disallowedLicenses:
            return licenseFile.spdx_id,"bad"
        else:
            print(licenseFile.name)
            return licenseFile.spdx_id,"unknown"
    except:
        return False, "unknown"


