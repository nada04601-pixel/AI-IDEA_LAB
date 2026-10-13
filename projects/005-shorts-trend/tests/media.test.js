import { test } from 'node:test';
import assert from 'node:assert/strict';
import { youtubeIdFrom, isImageUrl, youtubeThumbnails } from '../src/media.js';

test('youtubeIdFrom: 여러 주소 형식에서 영상 ID를 뽑는다', () => {
  const id = 'dQw4w9WgXcQ';
  for (const url of [
    `https://www.youtube.com/shorts/${id}`,
    `https://youtube.com/shorts/${id}?feature=share`,
    `https://m.youtube.com/watch?v=${id}&t=10`,
    `https://youtu.be/${id}?si=abc`,
    `youtube.com/embed/${id}`,
    `https://www.youtube.com/live/${id}`,
    id,
  ]) assert.equal(youtubeIdFrom(url), id, url);
  for (const bad of ['', 'https://example.com/shorts/dQw4w9WgXcQ', 'https://youtube.com/@channel', 'hello world', 'https://youtu.be/short']) {
    assert.equal(youtubeIdFrom(bad), null, bad);
  }
});

test('isImageUrl: https 이미지 주소만', () => {
  assert.ok(isImageUrl('https://i.ytimg.com/vi/x/hqdefault.jpg'));
  assert.ok(isImageUrl('https://a.com/b.webp?x=1'));
  assert.ok(!isImageUrl('http://a.com/b.jpg'));
  assert.ok(!isImageUrl('javascript:alert(1)//.png'));
  assert.ok(!isImageUrl('https://a.com/video.mp4'));
});

test('youtubeThumbnails: 큰 것부터', () => {
  assert.deepEqual(youtubeThumbnails('abc'), ['https://i.ytimg.com/vi/abc/maxresdefault.jpg', 'https://i.ytimg.com/vi/abc/hqdefault.jpg']);
});
