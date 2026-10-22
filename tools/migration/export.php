<?php
// Run over SSH stdin. Credentials remain on the source server; all queries are read-only.
mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);
$root = getenv('WP_ROOT') ?: '/home/wwwroot/blog.dalaoweb.top';
$config = file_get_contents($root . '/wp-config.php');
preg_match_all('~define\s*\(\s*([\'"])(DB_NAME|DB_USER|DB_PASSWORD|DB_HOST)\1\s*,\s*([\'"])(.*?)\3\s*\)~s', $config, $matches, PREG_SET_ORDER);
$credentials = [];
foreach ($matches as $match) {
    $credentials[$match[2]] = $match[3] === "'"
        ? str_replace(["\\\\", "\\'"], ["\\", "'"], $match[4])
        : stripcslashes($match[4]);
}
preg_match('~\$table_prefix\s*=\s*[\'"]([a-zA-Z0-9_]+)[\'"]~', $config, $prefixMatch);
if (count($credentials) !== 4 || empty($prefixMatch[1])) {
    fwrite(STDERR, "Unsupported source configuration. No data exported.\n");
    exit(1);
}
$prefix = $prefixMatch[1];
$db = new mysqli($credentials['DB_HOST'], $credentials['DB_USER'], $credentials['DB_PASSWORD'], $credentials['DB_NAME']);
$db->set_charset('utf8mb4');
$db->query('SET SESSION TRANSACTION READ ONLY');
$db->begin_transaction(MYSQLI_TRANS_START_WITH_CONSISTENT_SNAPSHOT);
$rows = function ($sql) use ($db) { return $db->query($sql)->fetch_all(MYSQLI_ASSOC); };
$terms = $rows("SELECT t.term_id AS id,t.name,t.slug,tt.taxonomy,tt.parent FROM {$prefix}terms t JOIN {$prefix}term_taxonomy tt ON tt.term_id=t.term_id WHERE tt.taxonomy IN ('category','post_tag')");
$termMap = [];
$blockedCategories = [];
$blockedTags = [];
foreach ($terms as &$term) {
    $term['id'] = (int) $term['id'];
    $term['parent'] = (int) $term['parent'];
    $termMap[$term['taxonomy'] . ':' . $term['id']] = $term;
    if ($term['taxonomy'] === 'category' && $term['slug'] === 'r18') {
        $blockedCategories[] = $term['id'];
    }
    if ($term['taxonomy'] === 'post_tag' && $term['slug'] === 'h') {
        $blockedTags[] = $term['id'];
    }
}
unset($term);
if (!$blockedCategories) {
    fwrite(STDERR, "Required exclusion category missing. No data exported.\n");
    exit(1);
}
do {
    $changed = false;
    foreach ($terms as $term) {
        if ($term['taxonomy'] === 'category' && in_array($term['parent'], $blockedCategories, true) && !in_array($term['id'], $blockedCategories, true)) {
            $blockedCategories[] = $term['id'];
            $changed = true;
        }
    }
} while ($changed);
$blockedIds = implode(',', array_merge($blockedCategories, $blockedTags));
$eligible = "p.post_type IN ('post','page') AND p.post_status='publish' AND p.post_password='' AND NOT EXISTS (SELECT 1 FROM {$prefix}term_relationships tr JOIN {$prefix}term_taxonomy tt ON tt.term_taxonomy_id=tr.term_taxonomy_id WHERE tr.object_id=p.ID AND ((tt.taxonomy='category' AND tt.term_id IN (" . implode(',', $blockedCategories) . "))" . ($blockedTags ? " OR (tt.taxonomy='post_tag' AND tt.term_id IN (" . implode(',', $blockedTags) . "))" : '') . '))';
$posts = $rows("SELECT p.ID AS id,p.post_type AS type,p.post_status AS status,p.post_title AS title,p.post_content AS content,p.post_excerpt AS excerpt,p.post_date AS date,p.post_date_gmt AS date_gmt,p.post_modified AS modified,p.post_name AS slug,p.post_parent AS parent FROM {$prefix}posts p WHERE {$eligible} ORDER BY p.post_date,p.ID");
$postIds = array_column($posts, 'id');
if (!$postIds) { throw new RuntimeException('No eligible public content.'); }
$relationships = $rows("SELECT tr.object_id,tt.term_id,tt.taxonomy FROM {$prefix}term_relationships tr JOIN {$prefix}term_taxonomy tt ON tt.term_taxonomy_id=tr.term_taxonomy_id WHERE tr.object_id IN (" . implode(',', array_map('intval', $postIds)) . ") AND tt.taxonomy IN ('category','post_tag')");
$byPost = [];
$usedTerms = [];
foreach ($relationships as $relationship) {
    $byPost[(int) $relationship['object_id']][] = (int) $relationship['term_id'];
    $key = $relationship['taxonomy'] . ':' . $relationship['term_id'];
    $term = $termMap[$key];
    $usedTerms[$key] = $term;
    while ($term['taxonomy'] === 'category' && $term['parent']) {
        $key = 'category:' . $term['parent'];
        if (isset($usedTerms[$key])) { break; }
        $term = $termMap[$key];
        $usedTerms[$key] = $term;
    }
}
$thumbnails = [];
foreach ($rows("SELECT post_id,meta_value FROM {$prefix}postmeta WHERE meta_key='_thumbnail_id' AND post_id IN (" . implode(',', array_map('intval', $postIds)) . ')') as $thumbnail) {
    $thumbnails[(int) $thumbnail['post_id']] = (int) $thumbnail['meta_value'];
}
$options = [];
foreach ($rows("SELECT option_name,option_value FROM {$prefix}options WHERE option_name IN ('home','blogname','blogdescription','timezone_string','gmt_offset','ossdl_off_cdn_url')") as $option) {
    $options[$option['option_name']] = $option['option_value'];
}
$base = rtrim($options['home'], '/');
$timezoneName = $options['timezone_string'] ?: 'Asia/Shanghai';
$sourceTimezone = new DateTimeZone($timezoneName);
$sourceOffsetHours = $sourceTimezone->getOffset(new DateTimeImmutable('now', $sourceTimezone)) / 3600;
$attachmentIds = array_values($thumbnails);
$categoryPath = function ($term) use ($termMap) {
    $path = [$term['slug']];
    $seen = [$term['id']];
    while ($term['parent'] && !in_array($term['parent'], $seen, true)) {
        $seen[] = $term['parent'];
        $term = $termMap['category:' . $term['parent']];
        array_unshift($path, $term['slug']);
    }
    return implode('/', $path);
};
foreach ($posts as &$post) {
    $post['id'] = (int) $post['id'];
    $post['parent'] = (int) $post['parent'];
    $post['password'] = '';
    $post['term_ids'] = $byPost[$post['id']] ?? [];
    $post['thumbnail_id'] = $thumbnails[$post['id']] ?? 0;
    $categories = [];
    foreach ($post['term_ids'] as $termId) {
        if (isset($termMap['category:' . $termId])) { $categories[] = $termMap['category:' . $termId]; }
    }
    usort($categories, function ($a, $b) { return $a['id'] <=> $b['id']; });
    $post['link'] = $post['type'] === 'post'
        ? $base . '/' . ($categories ? $categoryPath($categories[0]) : 'uncategorized') . '/' . $post['id'] . '/'
        : $base . '/' . trim($post['slug'], '/') . '/';
    preg_match_all('~(?:wp-image-|attachment_)(\d+)~', $post['content'], $referenced);
    foreach ($referenced[1] as $id) { $attachmentIds[] = (int) $id; }
    preg_match_all('~\[gallery\b[^\]]*\bids=[\'"]([\d, ]+)[\'"]~', $post['content'], $galleries);
    foreach ($galleries[1] as $ids) { foreach (explode(',', $ids) as $id) { $attachmentIds[] = (int) $id; } }
}
unset($post);
$attachmentIds = array_values(array_unique(array_filter($attachmentIds)));
$attachments = $rows("SELECT ID AS id,guid AS url,post_parent AS parent,post_mime_type AS mime FROM {$prefix}posts WHERE post_type='attachment' AND (post_parent IN (" . implode(',', array_map('intval', $postIds)) . ')' . ($attachmentIds ? ' OR ID IN (' . implode(',', $attachmentIds) . ')' : '') . ')');
$attachmentMap = [];
foreach ($attachments as &$attachment) {
    $attachment['id'] = (int) $attachment['id'];
    $attachment['parent'] = (int) $attachment['parent'];
    $attachmentMap[$attachment['id']] = &$attachment;
}
unset($attachment);
if ($attachments) {
    foreach ($rows("SELECT post_id,meta_value FROM {$prefix}postmeta WHERE meta_key='_wp_attached_file' AND post_id IN (" . implode(',', array_column($attachments, 'id')) . ')') as $file) {
        $attachmentMap[(int) $file['post_id']]['file'] = $file['meta_value'];
    }
}
$counts = $rows("SELECT post_type AS type,post_status AS status,(post_password<>'') AS protected,COUNT(*) AS count FROM {$prefix}posts WHERE post_type IN ('post','page') GROUP BY post_type,post_status,protected");
// Exclusion identifiers support converter fail-closed checks; no excluded titles or bodies are exported.
foreach ($terms as $term) {
    if (in_array($term['id'], $blockedCategories, true) || in_array($term['id'], $blockedTags, true)) {
        $usedTerms[$term['taxonomy'] . ':' . $term['id']] = $term;
    }
}
$result = [
    'schema_version' => 1,
    'site' => [
        'base_url' => $base,
        'title' => $options['blogname'],
        'description' => $options['blogdescription'],
        'timezone' => $timezoneName,
        'utc_offset_hours' => $sourceOffsetHours,
        'upload_base_url' => $base . '/wp-content/uploads/',
        'cdn_base_url' => rtrim($options['ossdl_off_cdn_url'] ?? 'https://cdn.dalaoweb.top', '/'),
    ],
    'terms' => array_values($usedTerms),
    'posts' => $posts,
    'attachments' => $attachments,
    'export_summary' => ['public_exported' => count($posts), 'source_counts' => $counts, 'blocked_category_ids' => $blockedCategories, 'blocked_tag_ids' => $blockedTags, 'comments_exported' => 0],
];
$db->rollback();
echo json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR), "\n";
