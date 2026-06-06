import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';

import '../models/synkora_models.dart';

class SynkoraApiException implements Exception {
  const SynkoraApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

class SynkoraApiClient {
  SynkoraApiClient({required String baseUrl, this.accessTokenProvider})
    : _dio = Dio(
        BaseOptions(
          baseUrl: baseUrl,
          connectTimeout: const Duration(seconds: 15),
          receiveTimeout: const Duration(seconds: 60),
          headers: const {'Content-Type': 'application/json'},
        ),
      );

  final Dio _dio;
  final String? Function()? accessTokenProvider;

  Future<Map<String, dynamic>> getJson(
    String path, {
    Map<String, dynamic>? queryParameters,
    bool authenticated = true,
  }) async {
    try {
      final response = await _dio.get<Map<String, dynamic>>(
        path,
        queryParameters: queryParameters,
        options: Options(headers: _headers(authenticated: authenticated)),
      );
      return response.data ?? const {};
    } on DioException catch (error) {
      throw _wrapDioException(error);
    }
  }

  Future<Map<String, dynamic>> postJson(
    String path, {
    Object? data,
    bool authenticated = true,
    Map<String, dynamic>? headers,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        path,
        data: data,
        options: Options(
          headers: _headers(authenticated: authenticated, extra: headers),
        ),
      );
      return response.data ?? const {};
    } on DioException catch (error) {
      throw _wrapDioException(error);
    }
  }

  Future<Map<String, dynamic>> postMultipart(
    String path, {
    required FormData data,
    bool authenticated = true,
    Map<String, dynamic>? headers,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        path,
        data: data,
        options: Options(
          contentType: 'multipart/form-data',
          headers: _headers(authenticated: authenticated, extra: headers),
        ),
      );
      return response.data ?? const {};
    } on DioException catch (error) {
      throw _wrapDioException(error);
    }
  }

  Stream<ChatEvent> postEventStream(
    String path, {
    required Map<String, dynamic> data,
    bool authenticated = true,
  }) {
    final controller = StreamController<ChatEvent>();

    () async {
      try {
        final response = await _dio.post<ResponseBody>(
          path,
          data: data,
          options: Options(
            responseType: ResponseType.stream,
            headers: _headers(
              authenticated: authenticated,
              extra: const {'Accept': 'text/event-stream'},
            ),
          ),
        );

        final buffer = StringBuffer();
        await for (final bytes in response.data!.stream) {
          buffer.write(utf8.decode(bytes));
          final raw = buffer.toString();
          final blocks = raw.split('\n\n');
          buffer.clear();
          buffer.write(blocks.last);

          for (var index = 0; index < blocks.length - 1; index++) {
            final block = blocks[index].trim();
            if (block.isEmpty) continue;

            String? dataLine;
            for (final line in block.split('\n')) {
              if (line.startsWith('data:')) {
                dataLine = line.substring(5).trim();
                break;
              }
            }

            if (dataLine == null || dataLine.isEmpty || dataLine == '[DONE]') {
              continue;
            }

            try {
              final parsed = jsonDecode(dataLine) as Map<String, dynamic>;
              final event = ChatEvent.fromJson(parsed);
              controller.add(event);
              if (event.type == 'error') {
                await controller.close();
                return;
              }
            } catch (_) {
              continue;
            }
          }
        }
      } on DioException catch (error) {
        controller.addError(_wrapDioException(error));
      } catch (error) {
        controller.addError(
          SynkoraApiException('Failed to stream agent response: $error'),
        );
      } finally {
        await controller.close();
      }
    }();

    return controller.stream;
  }

  Map<String, dynamic> _headers({
    required bool authenticated,
    Map<String, dynamic>? extra,
  }) {
    final headers = <String, dynamic>{};
    if (authenticated) {
      final token = accessTokenProvider?.call();
      if (token == null || token.isEmpty) {
        throw const SynkoraApiException('Authentication required.');
      }
      headers['Authorization'] = 'Bearer $token';
    }
    if (extra != null) {
      headers.addAll(extra);
    }
    return headers;
  }

  SynkoraApiException _wrapDioException(DioException error) {
    final statusCode = error.response?.statusCode;
    final responseData = error.response?.data;
    if (responseData is Map<String, dynamic>) {
      final detail = responseData['detail'];
      if (detail is Map<String, dynamic>) {
        final message = detail['message']?.toString();
        if (message != null && message.isNotEmpty) {
          return SynkoraApiException(message, statusCode: statusCode);
        }
      }
      final message =
          responseData['message']?.toString() ??
          responseData['detail']?.toString();
      if (message != null && message.isNotEmpty) {
        return SynkoraApiException(message, statusCode: statusCode);
      }
    }
    return SynkoraApiException(
      error.message ?? 'Unexpected network error',
      statusCode: statusCode,
    );
  }
}
