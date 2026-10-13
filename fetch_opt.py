import json, urllib.request, os, sys
url = ('https://api.openalex.org/works?filter='
       'primary_location.source.issn:0022-1082,'
       'primary_location.source.is_core:true,'
       'title_and_abstract.search:%22option%20pricing%22,'
       'from_publication_date:2015-01-01'
       '&sort=cited_by_count:desc'
       '&per-page=20'
       '&select=doi,title,publication_year,cited_by_count,authorships,primary_location'
       '&api_key=' + os.getenv('OPENALEX_API_KEY'))
with urllib.request.urlopen(url) as resp:
    data = json.load(resp)
results = data.get('results', [])
meta = data.get('meta', {})
count = meta.get('count', 0)
lines = []
lines.append('# literature.md')
lines.append('')
lines.append(f'搜尋條件：關鍵字 **option pricing**、期刊 **The Journal of Finance**（ISSN 0022-1082）、起始年份 **2015**、共 {count} 筆（顯示前 {min(len(results),20)} 筆）')
lines.append('')
lines.append('| 年份 | 作者 | 標題 | 期刊 | 被引數 | DOI |')
lines.append('|---|---|---|---|---|---|')
for r in results:
    year = r.get('publication_year','')
    title = r.get('title','').replace('\n',' ')
    doi = r.get('doi','')
    doi_url = f'https://doi.org/{doi}' if doi and not doi.startswith('http') else doi
    # authors
    auths = r.get('authorships', [])
    names = [a.get('author',{}).get('display_name','') for a in auths]
    if len(names) > 3:
        authors = ', '.join(names[:3]) + ' 等'
    else:
        authors = ', '.join(names)
    # journal name
    journal = r.get('primary_location',{}).get('source',{}).get('display_name','')
    cited = r.get('cited_by_count','')
    line = f'| {year} | {authors} | {title} | {journal} | {cited} | {doi_url} |'
    lines.append(line)
lines.append('')
lines.append('查詢網址（已遮蔽金鑰）：')
lines.append(url.replace(os.getenv('OPENALEX_API_KEY',''), '***'))
with open('literature.md','w',encoding='utf-8') as f:
    f.write('\n'.join(lines))
print('done')
