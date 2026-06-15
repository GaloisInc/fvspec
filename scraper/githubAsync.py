import datetime
import asyncio
import aiohttp


class License:
    spdx_id: str
    name: str

    def __init__(self, spdx_id, name):
        self.spdx_id = spdx_id
        self.name = name


class Repository:
    full_name: str
    clone_url: str
    license: License | None
    stars: int
    forks: int

    def __init__(
        self, name: str, license: License | None = None, stars: int = 0, forks: int = 0
    ):
        self.full_name = name
        self.name = name.split("/")[1]
        self.clone_url = f"https://github.com/{name}.git"
        self.license = license
        self.stars = stars
        self.forks = forks


async def asyncSleep(time: str, cause: str | None = None):
    ts = datetime.datetime.fromtimestamp(int(time))
    # get number of seconds from now until ts
    delta = ts - datetime.datetime.now()
    rounded = round(delta.total_seconds()) + 1
    print(f"Sleeping for {rounded} seconds {f'due to {cause}' if cause else ''}")
    await asyncio.sleep(rounded)
    return


concurency = 2
sem = asyncio.Semaphore(concurency)


async def useRateLimit(response):
    json = await response.json()
    rate_limit = response.headers.get("X-RateLimit-Remaining")
    reset_time = response.headers.get("X-RateLimit-Reset")
    if rate_limit and int(rate_limit) < concurency:
        if reset_time:
            await asyncSleep(
                reset_time,
                f"rate limit: {rate_limit}, reset time: {reset_time}, used: {response.headers.get('X-RateLimit-Used')}",
            )
            return True
    elif "message" in json and "secondary rate limit" in json["message"]:
        if reset_time:
            await asyncSleep(
                reset_time,
                f"secondary rate limit: {rate_limit}, reset time: {reset_time}",
            )
            return True
        else:
            print(json)
            await asyncSleep("60", "other")
            return True


async def search_repositories_async(session: aiohttp.ClientSession, auth, query: str):
    url = "https://api.github.com/search/repositories"
    params = {"q": query, "per_page": 10}

    async with (
        sem,
        session.get(
            url, params=params, headers={"Authorization": f"Bearer {auth}"}
        ) as response,
    ):
        print(f"got response for {query}")
        json = await response.json()
        if await useRateLimit(response):
            return await search_repositories_async(session, auth, query)
        if "items" not in json:
            return []
        repositories = json["items"]
        results: list[Repository] = []
        for repo in repositories:
            results.append(
                Repository(
                    repo["full_name"],
                    license=License(repo["license"]["spdx_id"], repo["license"]["name"])
                    if repo["license"]
                    else None,
                    stars=repo["stargazers_count"],
                    forks=repo["forks_count"],
                )
            )
        return results


# https://docs.github.com/en/rest/repos/repos#get-a-repository
async def get_repository_async(session: aiohttp.ClientSession, auth, full_name: str):
    url = f"https://api.github.com/repos/{full_name}"
    async with (
        sem,
        session.get(url, headers={"Authorization": f"Bearer {auth}"}) as response,
    ):
        json = await response.json()
        if await useRateLimit(response):
            return await get_repository_async(session, auth, full_name)
        if response.status != 200:
            print(json)
        if "full_name" not in json:
            return None
        return Repository(
            json["full_name"],
            license=License(json["license"]["spdx_id"], json["license"]["name"])
            if json["license"]
            else None,
            stars=json["stargazers_count"],
            forks=json["forks_count"],
        )
