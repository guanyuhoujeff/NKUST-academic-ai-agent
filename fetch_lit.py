import json, pathlib
path = r'C:/Users/mycena/.local/share/opencode/tool-output/tool_11a9eafe2001q4r3CbThwjZvtB'
with open(path, encoding='utf-8') as f:
    data = json.load(f)
results = data.get('results', [])
lines = []
lines.append('# literature.md')
lines.append('')
keyword = 'option pricing'
issn = '0022-1082'
journal_name = 'The Journal of Finance'
start_year = 2015
meta_count = data.get('meta',{}).get('count',0)
lines.append(f'搜尋條件：關鍵字 **{keyword}**、期刊 **{journal_name}**（ISSN {issn}）、起始年份 **{start_year}**、共 {meta_count} 筆（顯示前 {len(results)} 筆）')
lines.append('')
lines.append('| 年份 | 作者 | 標題 | 期刊 | 被引數 | DOI |')
lines.append('|---|---|---|---|---|---|')
for r in results:
    year = r.get('publication_year','')
    doi = r.get('doi','')
    cited = r.get('cited_by_count','')
    title = r.get('title','').replace('|','\\|')
    auths = r.get('authorships', [])
    names = [a.get('author',{}).get('display_name','') for a in auths[:3] if a.get('author')]
    if len(auths) > 3:
        names.append('等')
    authors = ', '.join(names)
    lines.append(f'| {year} | {authors} | {title} | {journal_name} | {cited} | {doi} |')
lines.append('')
lines.append('查詢網址（已遮蔽金鑰）：')
lines.append('https://api.openalex.org/works?filter=primary_location.source.issn:0022-1082,primary_location.source.is_core:true,title_and_abstract.search:%22option%20pricing%22,from_publication_date:2015-01-01&sort=cited_by_count:desc&per-page=10&select=doi,title,publication_year,cited_by_count,authorships,primary_location&api_key=***')
out_path = pathlib.Path('D:/ai-research/literature.md')
out_path.write_text('\n'.join(lines), encoding='utf-8')
print('done')
