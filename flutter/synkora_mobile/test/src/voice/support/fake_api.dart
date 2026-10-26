import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:synkora_mobile/src/services/api_client.dart';

class RecordingApi extends SynkoraApiClient {
  RecordingApi() : super(baseUrl: 'http://test');

  Map<String, dynamic> jsonResponse = const {};
  final Map<String, Map<String, dynamic>> jsonByPath = {};
  int getCount = 0;
  Uint8List bytesResponse = Uint8List(0);
  SynkoraApiException? failure;

  String? lastPath;
  Map<String, dynamic>? lastQuery;
  Object? lastBody;
  FormData? lastForm;

  @override
  Future<Map<String, dynamic>> getJson(
    String path, {
    Map<String, dynamic>? queryParameters,
    bool authenticated = true,
  }) async {
    lastPath = path;
    getCount++;
    if (failure != null) throw failure!;
    return jsonByPath[path] ?? jsonResponse;
  }

  @override
  Future<Map<String, dynamic>> postMultipart(
    String path, {
    required FormData data,
    Map<String, dynamic>? queryParameters,
    bool authenticated = true,
    Map<String, dynamic>? headers,
  }) async {
    lastPath = path;
    lastForm = data;
    lastQuery = queryParameters;
    if (failure != null) throw failure!;
    return jsonResponse;
  }

  @override
  Future<Uint8List> postForBytes(
    String path, {
    required Object data,
    bool authenticated = true,
    Duration receiveTimeout = const Duration(seconds: 60),
  }) async {
    lastPath = path;
    lastBody = data;
    if (failure != null) throw failure!;
    return bytesResponse;
  }
}
